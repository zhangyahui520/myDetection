from typing import List
import json
import torch

from .registry import get_backbone, get_fpn, get_rpn, get_det_layer
from utils.structures import ImageObjects


def name_to_model(model_name):
    from settings import PROJECT_ROOT
    cfg = json.load(open(f'{PROJECT_ROOT}/configs/{model_name}.json', 'r'))

    if cfg['base'] == 'OneStageBBox':
        model = OneStageBBox(cfg)
    elif cfg['base'] == 'SimpleVOD':
        from .vod import SimpleVOD
        model = SimpleVOD(cfg)
    elif cfg['base'] == 'FullRNNVOD':
        from .vod import FullRNNVOD
        model = FullRNNVOD(cfg)
    else:
        raise Exception('Unknown model name')
    
    return model, cfg


class OneStageBBox(torch.nn.Module):
    def __init__(self, cfg: dict):
        super().__init__()

        self.backbone = get_backbone(cfg)
        self.fpn = get_fpn(cfg)
        self.rpn = get_rpn(cfg)
        
        det_layer = get_det_layer(cfg)
        self.det_layers = torch.nn.ModuleList()
        for level_i in range(len(cfg['model.fpn.out_channels'])):
            self.det_layers.append(det_layer(level_i=level_i, cfg=cfg))

        self.check_gt_assignment = cfg.get('train.check_gt_assignment', False)
        self.bb_format = cfg.get('general.pred_bbox_format', 'cxcywh')
        self.input_format = cfg['general.input_format']

    def forward(self, x, labels: List[ImageObjects]=None):
        '''
        x: a batch of images, e.g. shape(8,3,608,608)
        labels: a batch of ground truth
        '''
        assert x.dim() == 4
        self.img_size = x.shape[2:4]

        # go through the backbone and the feature payamid network
        features = self.backbone(x)
        features = self.fpn(features)
        # for fi, f in enumerate(features):
        #     import cv2
        #     import matplotlib.pyplot as plt
        #     import numpy as np
        #     wh = f.shape[2]
        #     f[:,:,wh//3-3:wh//3+3,wh//3-3:wh//3+3] /= 10
        #     sum_f = f.abs().sum(dim=1).squeeze().cpu().numpy()
        #     plt.imshow(sum_f, cmap='gray'); plt.show()
        #     debug = 1
        #     break
        all_branch_preds = self.rpn(features)
        
        dts_all = []
        losses_all = []
        for i, raw_preds in enumerate(all_branch_preds):
            dts, loss = self.det_layers[i](raw_preds, self.img_size, labels)
            dts_all.append(dts)
            losses_all.append(loss)

        batch_bbs     = torch.cat([d['bbox']      for d in dts_all], dim=1)
        batch_cls_idx = torch.cat([d['class_idx'] for d in dts_all], dim=1)
        batch_scores  = torch.cat([d['score']     for d in dts_all], dim=1)

        batch_pred_objects = []
        # iterate over every image in the batch
        for bbs, cls_idx, scores in zip(batch_bbs, batch_cls_idx, batch_scores):
            # initialize the pred objects in current image
            p_objs = ImageObjects(bboxes=bbs, cats=cls_idx, scores=scores,
                                  bb_format=self.bb_format, img_hw=self.img_size)
            batch_pred_objects.append(p_objs)

        if labels is None:
            return batch_pred_objects

        if self.check_gt_assignment:
            total_gt_num = sum([len(t) for t in labels])
            assigned = sum(branch._assigned_num for branch in self.det_layers)
            assert assigned == total_gt_num, f'{assigned} != {total_gt_num}'
        self.loss_str = ''
        for m in self.det_layers:
            self.loss_str += m.loss_str + '\n'
        loss = sum(losses_all)
        return batch_pred_objects, loss
