# API for the object detectors
import os
import numpy as np
import cv2
from PIL import Image
import matplotlib.pyplot as plt
from tqdm import tqdm
from random import randint

import torch
import torchvision.transforms.functional as tvf

import utils.utils as Utils
import utils.visualization as visUtils


class Detector():
    def __init__(self, model_name=None, weights_path=None, model=None, conf_thres=0.5):
        assert torch.cuda.is_available()
        if model:
            self.model = model
        elif model_name == 'yolov3':
            from models.yolov3 import YOLOv3
            model = YOLOv3(class_num=80, backbone='dark53', img_norm=False)
        else:
            raise Exception('Unknown model name')
        # total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        # print('Number of parameters:', total_params)
        if weights_path:
            model.load_state_dict(torch.load(weights_path)['model'])
        self.model = model.cuda()

        self.conf_thres = conf_thres
    
    def detect_one(self, **kwargs): # img_path, test_aug=None, input_size=1024):
        '''
        object detection in one single image. Predict and show the results

        Args:
            (img_path: str) or (pil_img: PIL.Image)
            visualize: bool, default: True
            See _predict_pil() for optinal arguments
        '''
        self.model.eval()
        if 'img_path' in kwargs:
            img = Utils.imread_pil(kwargs['img_path'])
        else:
            assert 'pil_img' in kwargs
            img = kwargs.pop('pil_img')

        detections = self._predict_pil(img, **kwargs)

        if kwargs.get('visualize', True):
            np_img = np.array(img)
            visUtils.draw_cocobb_on_np(np_img, detections, 'pbb', print_dt=True)
            plt.imshow(np_img)
            plt.show()
        return detections
        
    def predict_imgDir(self, img_dir, **kwargs):
        '''
        Run the object detector on a sequence of images
        
        Args:
            img_dir: str
            See _predict_pil() for optinal arguments
        '''
        self.model.eval()
        img_names = os.listdir(img_dir)
        detection_json = []
        for imname in tqdm(img_names):
            assert imname[-4] == '.'
            img_id = int(imname[:-4]) if imname[:-4].isdigit() else imname[:-4]
            impath = os.path.join(img_dir, imname)
            img = Utils.imread_pil(impath)

            detections = self._predict_pil(img, **kwargs)
            for dt in detections:
                cls_idx, cx, cy, w, h, conf = [float(t) for t in dt]
                bbox = [cx-w/2, cy-h/2, w, h]
                cat_id = Utils.COCO_CATEGORY_LIST[int(cls_idx)]['id']
                dt_dict = {'image_id': img_id, 'category_id': cat_id,
                           'bbox': bbox, 'score': conf}
                detection_json.append(dt_dict)

        return detection_json
    
    def _predict_pil(self, pil_img, **kwargs):
        '''
        Args:
            test_aug: str, test-time augmentation, can be: 'h'
            input_size: int, default: 640
            conf_thres: float, confidence threshold
        '''
        test_aug = kwargs['test_aug'] if 'test_aug' in kwargs else None
        input_size = kwargs['input_size'] if 'input_size' in kwargs else 640
        conf_thres = kwargs['conf_thres'] if 'conf_thres' in kwargs else self.conf_thres
        assert isinstance(pil_img, Image.Image), 'input must be a PIL.Image'

        # pad to square
        input_img, _, pad_info = Utils.rect_to_square(pil_img, None, input_size)
        
        input_ori = tvf.to_tensor(input_img)
        if not test_aug:
            input_ = input_ori.unsqueeze(0)
        elif test_aug == 'h':
            raise Exception('Deprecated')
            # horizontal flip
            input_hflip = input_ori.flip(2)
            input_ = torch.stack([input_ori, input_hflip], dim=0)
        else:
            raise Exception('Invalid test-time augmentation')
        
        assert input_.dim() == 4
        with torch.no_grad():
            dts = self.model(input_.cuda()).cpu()

        if not test_aug:
            dts = dts.squeeze()
            # post-processing
            dts = dts[dts[:,5] >= conf_thres]
            if len(dts) > 1000:
                _, idx = torch.topk(dts[:,5], k=1000)
                dts = dts[idx, :]
            dts = Utils.nms(dts, bb_format='cxcywh', nms_thres=0.45)
            # np_img = np.array(tvf.to_pil_image(input_.squeeze()))
            # visualization.draw_cocobb_on_np(np_img, dts, print_dt=True)
            # plt.imshow(np_img)
            # plt.show()
            dts = Utils.detection2original(dts, pad_info.squeeze())
            return dts
        
        raise NotImplementedError()
