import torch
import numpy as np
import cv2
import matplotlib.pyplot as plt

from .constants import COCO_CATEGORY_LIST


def drawline(img, pt1, pt2, color, thickness=1, style='dotted', gap=15):
    dist =((pt1[0]-pt2[0])**2+(pt1[1]-pt2[1])**2)**.5
    pts= []
    for i in  np.arange(0,dist,gap):
        r=i/dist
        x=int((pt1[0]*(1-r)+pt2[0]*r)+.5)
        y=int((pt1[1]*(1-r)+pt2[1]*r)+.5)
        p = (x,y)
        pts.append(p)

    if style=='dotted':
        for p in pts:
            cv2.circle(img,p,thickness,color,-1)
    else:
        raise NotImplementedError()
        s=pts[0]
        e=pts[0]
        i=0
        for p in pts:
            s=e
            e=p
            if i%2==1:
                cv2.line(img,s,e,color,thickness)
            i+=1

def drawpoly(img,pts,color,thickness=1,style='dotted',):
    s=pts[0]
    e=pts[0]
    pts.append(pts.pop(0))
    for p in pts:
        s=e
        e=p
        drawline(img,s,e,color,thickness,style)


def _draw_xywha(im, x, y, w, h, angle, color=(255,0,0), linewidth=5,
                linestyle='-'):
    '''Draw a single rotated bbox on an image in-place.

    Args:
        im: image numpy array, shape(h,w,3), preferably RGB
        x, y, w, h: center xy, width, and height of the bounding box
        angle: degrees that the bounding box rotated clockwisely
        color (optional): tuple in 0~255 range
        linewidth (optional): with of the lines
        linestyle (optional): '-' for solid lines, and ':' for dotted lines
    
    Returns:
        None
    '''
    c, s = np.cos(angle/180*np.pi), np.sin(angle/180*np.pi)
    R = np.asarray([[c, s], [-s, c]])
    pts = np.asarray([[-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]])
    rot_pts = []
    for pt in pts:
        rot_pts.append(([x, y] + pt @ R).astype(int))
    if linestyle == '-':
        contours = np.array([rot_pts[0], rot_pts[1], rot_pts[2], rot_pts[3]])
        cv2.polylines(im, [contours], isClosed=True, color=color,
                    thickness=linewidth, lineType=cv2.LINE_4)
    elif linestyle == ':':
        contours = [rot_pts[0], rot_pts[1], rot_pts[2], rot_pts[3]]
        drawpoly(im, contours, color, thickness=linewidth)
    else:
        raise Exception('Unknown linestyle in function _draw_xywha()')


def draw_cocobb_on_np(im, bboxes, bb_type='pbb', print_dt=False):
    '''
    im: numpy array, uint8, shape(h,w,3), RGB
    bboxes: rows of [class,x,y,w,h,conf]
    '''
    raise DeprecationWarning()

    assert bboxes.dim() == 2 and bboxes.shape[1] >= 5
    line_width = round(im.shape[0] / 300)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = im.shape[0] * im.shape[1] / (700*700)
    font_bold = im.shape[0] // 400
    for bb in bboxes:
        if bb_type == 'gtbb':
            # ground truth BB
            cat_idx,x,y,w,h = bb
            a = 0
            conf = -1
        elif bb_type == 'pbb':
            # predicted BB
            cat_idx,x,y,w,h,conf = bb
            a = 0
        elif bb_type == 'gtrbb':
            # ground truth rotated BB
            cat_idx,x,y,w,h,a, = bb
            conf = -1
        elif bb_type == 'prbb':
            # predicted rotated BB
            cat_idx,x,y,w,h,a,conf = bb
        else:
            raise NotImplementedError()
        cat_idx = int(cat_idx)
        cat_name = COCO_CATEGORY_LIST[cat_idx]['name']
        cat_color = COCO_CATEGORY_LIST[cat_idx]['color']
        if print_dt:
            print(f'category:{cat_name}, score: {conf},',
                  f'[{x:.1f} {y:.1f} {w:.1f} {h:.1f} {a:.1f}].')
        _draw_xywha(im, x, y, w, h, a, color=cat_color, linewidth=line_width)
        x1, y1 = x - w/2, y - h/2
        text = cat_name if 'gt' in bb_type else f'{cat_name}, {conf:.2f}'
        cv2.putText(im, text, (int(x1),int(y1)), font, 0.5,
                    (255,255,255), font_bold, cv2.LINE_AA)
    # plt.imshow(im)
    # plt.show()


def draw_bboxes_on_np(im, img_objs, class_map='COCO', **kwargs):
    print_dt = kwargs.get('print_dt', False)
    color = kwargs.get('color', None)
    # Extract bboxes, scores, and category indices
    obj_num = img_objs.bboxes.shape[0]
    if obj_num == 0: return
    bboxes = img_objs.bboxes
    scores = img_objs.scores if img_objs.scores is not None else \
             [None for _ in range(obj_num)]
    class_indices = img_objs.cats
    assert len(bboxes) == len(scores) == len(class_indices)
    # Select the target dataset
    if class_map == 'COCO':
        cat_idx2name = lambda x: COCO_CATEGORY_LIST[x]['name']
        cat_idx2color = lambda x: COCO_CATEGORY_LIST[x]['color']
    else: raise NotImplementedError()
    # Initialize some drawing parameters
    line_width = round(im.shape[0] / 300)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = np.sqrt(im.shape[0] * im.shape[1]) / 2048
    font_bold = im.shape[0] // 600
    # Interate over all bounding boxes
    for bb, conf, c_idx in zip(bboxes, scores, class_indices):
        if img_objs._bb_format == 'cxcywh':
            cx, cy, w, h = bb
            a = 0
        elif img_objs._bb_format == 'cxcywhd':
            cx, cy, w, h, a = bb
        else: raise NotImplementedError()
        cat_name = cat_idx2name(c_idx)
        if color is None:
            cat_color = cat_idx2color(c_idx)
        else:
            cat_color = color
        if print_dt:
            print(f'category:{cat_name}, score: {conf},',
                  f'[{cx:.1f} {cy:.1f} {w:.1f} {h:.1f} {a:.1f}].')
        _draw_xywha(im, cx, cy, w, h, a, color=cat_color, linewidth=line_width)
        if kwargs.get('put_text', True):
            x1, y1 = cx - w/2, cy - h/2
            text = cat_name if conf is None else f'{cat_name}, {conf:.2f}'
            text = cat_name if conf is None else f'{conf:.2f}'
            cv2.putText(im, text, (int(x1),int(y1)), font, font_scale,
                        (255,255,255), font_bold, cv2.LINE_AA)
    if kwargs.get('imshow', False):
        plt.figure(figsize=(10,10))
        plt.imshow(im)
        plt.show()


def random_colors(num, order='rgb', dtype='uint8') -> np.ndarray:
    '''
    Generate random distinct colors
    '''
    assert isinstance(num, int) and num >= 1
    hues = np.linspace(0, 360, num+1, dtype=np.float32)
    np.random.shuffle(hues)
    hsvs = np.ones((1,num,3), dtype=np.float32)
    hsvs[0,:,0] = 2 if num==1 else hues[:-1]
    if order == 'rgb':
        colors = cv2.cvtColor(hsvs, cv2.COLOR_HSV2RGB)
    elif order == 'bgr':
        colors = cv2.cvtColor(hsvs, cv2.COLOR_HSV2BGR)
    if dtype == 'uint8':
        colors = (colors * 255).astype(np.uint8)
    else:
        assert dtype == 'float' or dtype == 'float32'
    colors = colors.reshape(num,3)
    return colors


def tensor_to_npimg(tensor_img):
    tensor_img = tensor_img.squeeze()
    assert tensor_img.shape[0] == 3 and tensor_img.dim() == 3
    return tensor_img.permute(1,2,0).cpu().numpy()


def imshow_tensor(tensor_batch):
    batch = tensor_batch.clone().detach().cpu()
    if batch.dim() == 3:
        batch = batch.unsqueeze(0)
    for tensor_img in batch:
        np_img = tensor_to_npimg(tensor_img)
        plt.imshow(np_img)
    plt.show()


def plt_show(im):
    plt.imshow(im)
    plt.show()
