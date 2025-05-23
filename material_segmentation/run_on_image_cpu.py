<<<<<<< HEAD
#%%
import glob
from models.vgg import vgg16
from models.googlenet import googlenet
import numpy as np
import cv2
import matplotlib.pyplot as plt
import pandas as pd

import torch
import torch.nn as nn

import pydensecrf.densecrf as dcrf
import pydensecrf.utils as utils
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
color_palette = np.loadtxt(os.path.join(BASE_DIR, 'palette.txt')).astype(np.uint8)
os.makedirs(os.path.join(BASE_DIR, 'videos'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'images'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'results'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'labelmaps'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'fds_output'), exist_ok=True)

def color_image_w_masks(image, masks):
    image = image.astype(np.uint8)

    for index in range(23):
        mask = (masks == index).astype(np.uint8)
        if mask.sum() == 0:
            continue
        color = color_palette[index]
        mask = np.expand_dims(mask, axis=-1)
        mask = np.repeat(mask, 3, axis=-1)
        mask = mask * np.array(color).reshape((-1, 3)) + (1 - mask) * image
        mask = mask.astype(np.uint8)
        image = cv2.addWeighted(image, .5, mask, .5, 0)
    return image

def inference_on_whole_image(img, model):
    h, w, c = img.shape
    if h % 256 != 0:
        h_ = (h // 256 + 1) * 256
    else:
        h_ = h
    if w % 256 != 0:
        w_ = (w // 256 + 1) * 256
    else:
        w_ = w

    img = cv2.resize(img, (w_, h_))
    img = img.astype(np.float32).transpose(2, 0, 1)
    img[0, :, :] -= 104
    img[1, :, :] -= 117
    img[2, :, :] -= 124
    img = torch.FloatTensor(img)
    img = img.unsqueeze(0)  # 移除 .cuda()

    softmax = nn.Softmax(dim=1)

    nh = h_ // 256
    nw = w_ // 256
    prob = np.zeros((h_, w_, 23))

    for i in range(nh):
        for j in range(nw):
            img_patch = img[:, :, i*256:(i+1)*256, j*256:(j+1)*256]
            pred = model(img_patch)
            pred = softmax(pred).squeeze().cpu().numpy().transpose(1, 2, 0)  # 保留在 CPU
            pred = cv2.resize(pred, (256, 256))
            prob[i*256:(i+1)*256, j*256:(j+1)*256, :] = pred

    return prob

def multi_scale_inference(img, model):
    h, w, c = img.shape
    scales = [.5, 1, 1.5]
    prob = np.zeros((h, w, 23))

    for scale in scales:
        img_ = cv2.resize(img, (int(w*scale), int(h*scale)))
        prob_ = inference_on_whole_image(img_, model)
        prob += cv2.resize(prob_, (w, h))

    prob /= 3
    return prob

class DenseCRF(object):
    def __init__(self, iter_max, pos_w, pos_xy_std, bi_w, bi_xy_std, bi_rgb_std):
        self.iter_max = iter_max
        self.pos_w = pos_w
        self.pos_xy_std = pos_xy_std
        self.bi_w = bi_w
        self.bi_xy_std = bi_xy_std
        self.bi_rgb_std = bi_rgb_std

    def __call__(self, image, probmap):
        C, H, W = probmap.shape

        U = utils.unary_from_softmax(probmap)
        U = np.ascontiguousarray(U)

        image = np.ascontiguousarray(image)

        d = dcrf.DenseCRF2D(W, H, C)
        d.setUnaryEnergy(U)
        d.addPairwiseGaussian(sxy=self.pos_xy_std, compat=self.pos_w)
        d.addPairwiseBilateral(
            sxy=self.bi_xy_std, srgb=self.bi_rgb_std, rgbim=image, compat=self.bi_w
        )

        Q = d.inference(self.iter_max)
        Q = np.array(Q).reshape((C, H, W))

        return Q

#%%
model0 = googlenet
#model1 = vgg16

m0 = model0()
#m1 = model1()

#m1.load_state_dict(torch.load('minc-vgg16.pth'), strict=False)
#m1.eval()
m0.load_state_dict(torch.load(os.path.join(BASE_DIR, 'weights', 'minc-googlenet.pth'), 
                                weights_only=True), strict=False)
m0.eval()

torch.set_grad_enabled(False)

labels = open(os.path.join(BASE_DIR, 'categories.txt'), 'r').readlines()
labels = [i.strip() for i in labels]

postprocessor = DenseCRF(
    iter_max=10,
    pos_xy_std=1,
    pos_w=3,
    bi_xy_std=67,
    bi_rgb_std=3,
    bi_w=4,
)

# ------- projection -------
img_num = '20250329_193301'
img_path = os.path.join(os.path.dirname(BASE_DIR), 'realsense', 'projections', f'projection_{img_num}.jpg')
print(f"image path: {img_path}")
img = cv2.imread(img_path)

# ------- pointclouds -------
# img_num = '20250329_193301'
# point_path = os.path.join(os.path.dirname(BASE_DIR), 'realsense', 'pointclouds', f'pointcloud_{img_num}.csv')
point_path = os.path.join(BASE_DIR, 'results', f'pointcloud_with_objects.csv')
df = pd.read_csv(point_path)
        
# ------- image processing -------
img = cv2.resize(img, (512, 512))
prob0 = multi_scale_inference(img, m0)
prob = prob0 

prob = cv2.resize(prob, (640, 480))
img = cv2.resize(img, (640, 480))
prob = prob.transpose(2, 0, 1)
prob = postprocessor(img, prob)
labelmap = np.argmax(prob, axis=0)


# ------- drawing -------
plt.figure(figsize=(10, 10))
plt.imshow(img[:, :, ::-1])

plt.figure(figsize=(15, 15))

for i in range(23):
    mask = labelmap == i
    ax = plt.subplot(4, 6, i + 1)
    ax.set_title(labels[i])
    ax.imshow(img[:, :, ::-1])
    ax.imshow(mask.astype(np.float32), alpha=0.5)
    ax.axis("off")

plt.tight_layout()
plt.savefig(os.path.join(BASE_DIR, 'results', f"result_{img_num}.png"))
# plt.show()
np.savetxt(os.path.join(BASE_DIR, 'labelmaps', f"test_{img_num}_labelmap.txt"), labelmap, fmt='%d')



# save material in pointclouds csv
def get_material(row):
    u, v = int(row['u']), int(row['v'])
    # 注意 labelmap 的索引順序通常為 [v, u]，確保 v 與 u 在正確範圍內
    if 0 <= u < labelmap.shape[1] and 0 <= v < labelmap.shape[0]:
        label_index = labelmap[v, u]
        # 若 label_index 超出 labels 長度，則可以做防呆處理
        if label_index < len(labels):
            return labels[label_index]
        else:
            return ""
    else:
        return ""

df['material'] = df.apply(get_material, axis=1)
output_csv_path = os.path.join(os.path.dirname(BASE_DIR), 'realsense', 'pointclouds', f'pointcloud_{img_num}_with_material.csv')
df.to_csv(output_csv_path, index=False)
=======
#%%
import glob
import numpy as np
import cv2
import matplotlib.pyplot as plt
import pandas as pd
import torch
import torch.nn as nn
import pydensecrf.densecrf as dcrf
import pydensecrf.utils as utils
import os
from material_segmentation.models.vgg import vgg16
from material_segmentation.models.googlenet import googlenet

def color_image_w_masks(image, masks):
    image = image.astype(np.uint8)

    for index in range(23):
        mask = (masks == index).astype(np.uint8)
        if mask.sum() == 0:
            continue
        color_palette = np.loadtxt('palette.txt').astype(np.uint8)
        color = color_palette[index]
        mask = np.expand_dims(mask, axis=-1)
        mask = np.repeat(mask, 3, axis=-1)
        mask = mask * np.array(color).reshape((-1, 3)) + (1 - mask) * image
        mask = mask.astype(np.uint8)
        image = cv2.addWeighted(image, .5, mask, .5, 0)
    return image

def inference_on_whole_image(img, model):
    h, w, c = img.shape
    if h % 256 != 0:
        h_ = (h // 256 + 1) * 256
    else:
        h_ = h
    if w % 256 != 0:
        w_ = (w // 256 + 1) * 256
    else:
        w_ = w

    img = cv2.resize(img, (w_, h_))
    img = img.astype(np.float32).transpose(2, 0, 1)
    img[0, :, :] -= 104
    img[1, :, :] -= 117
    img[2, :, :] -= 124
    img = torch.FloatTensor(img)
    img = img.unsqueeze(0)  # 移除 .cuda()

    softmax = nn.Softmax(dim=1)

    nh = h_ // 256
    nw = w_ // 256
    prob = np.zeros((h_, w_, 23))

    for i in range(nh):
        for j in range(nw):
            img_patch = img[:, :, i*256:(i+1)*256, j*256:(j+1)*256]
            pred = model(img_patch)
            pred = softmax(pred).squeeze().cpu().numpy().transpose(1, 2, 0)  # 保留在 CPU
            pred = cv2.resize(pred, (256, 256))
            prob[i*256:(i+1)*256, j*256:(j+1)*256, :] = pred

    return prob

def multi_scale_inference(img, model):
    h, w, c = img.shape
    scales = [.5, 1, 1.5]
    prob = np.zeros((h, w, 23))

    for scale in scales:
        img_ = cv2.resize(img, (int(w*scale), int(h*scale)))
        prob_ = inference_on_whole_image(img_, model)
        prob += cv2.resize(prob_, (w, h))

    prob /= 3
    return prob

class DenseCRF(object):
    def __init__(self, iter_max, pos_w, pos_xy_std, bi_w, bi_xy_std, bi_rgb_std):
        self.iter_max = iter_max
        self.pos_w = pos_w
        self.pos_xy_std = pos_xy_std
        self.bi_w = bi_w
        self.bi_xy_std = bi_xy_std
        self.bi_rgb_std = bi_rgb_std

    def __call__(self, image, probmap):
        C, H, W = probmap.shape

        U = utils.unary_from_softmax(probmap)
        U = np.ascontiguousarray(U)

        image = np.ascontiguousarray(image)

        d = dcrf.DenseCRF2D(W, H, C)
        d.setUnaryEnergy(U)
        d.addPairwiseGaussian(sxy=self.pos_xy_std, compat=self.pos_w)
        d.addPairwiseBilateral(
            sxy=self.bi_xy_std, srgb=self.bi_rgb_std, rgbim=image, compat=self.bi_w
        )

        Q = d.inference(self.iter_max)
        Q = np.array(Q).reshape((C, H, W))

        return Q


# save material in pointclouds csv
def get_material(row, labelmap, labels):
    u, v = int(row['u']), int(row['v'])
    if 0 <= u < labelmap.shape[1] and 0 <= v < labelmap.shape[0]:
        label_index = labelmap[v, u]
        if label_index < len(labels):
            return labels[label_index]
        else:
            return ""
    else:
        return ""
    
#%%
def run_on_image_cpu(base_dir: str, img_num: str, img_path: str, point_path: str) -> dict:
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    os.makedirs(os.path.join(base_dir, 'videos'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'images'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'results'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'labelmaps'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'fds_output'), exist_ok=True)

    model0 = googlenet
    m0 = model0()
    m0.load_state_dict(torch.load(os.path.join(base_dir, 'weights', 'minc-googlenet.pth'), 
                                weights_only=True), strict=False)
    m0.eval()

    torch.set_grad_enabled(False)

    labels = open(os.path.join(base_dir, 'categories.txt'), 'r').readlines()
    labels = [i.strip() for i in labels]

    postprocessor = DenseCRF(
        iter_max=10,
        pos_xy_std=1,
        pos_w=3,
        bi_xy_std=67,
        bi_rgb_std=3,
        bi_w=4,
    )

    # ------- projection -------
    img = cv2.imread(img_path)

    # ------- pointclouds -------
    df = pd.read_csv(point_path)
            
    # ------- image processing -------
    img = cv2.resize(img, (512, 512))
    prob0 = multi_scale_inference(img, m0)
    prob = prob0 

    prob = cv2.resize(prob, (640, 480))
    img = cv2.resize(img, (640, 480))
    prob = prob.transpose(2, 0, 1)
    prob = postprocessor(img, prob)
    labelmap = np.argmax(prob, axis=0)

    # ------- drawing -------
    plt.figure(figsize=(15, 15))
    # plt.imshow(img[:, :, ::-1])

    for i in range(23):
        mask = labelmap == i
        ax = plt.subplot(4, 6, i + 1)
        ax.set_title(labels[i])
        ax.imshow(img[:, :, ::-1])
        ax.imshow(mask.astype(np.float32), alpha=0.5)
        ax.axis("off")

    plt.tight_layout()
    plt.savefig(os.path.join(base_dir, 'results', f"result_{img_num}.png"))
    np.savetxt(os.path.join(base_dir, 'labelmaps', f"test_{img_num}_labelmap.txt"), labelmap, fmt='%d')

    df['material'] = df.apply(lambda row: get_material(row, labelmap, labels), axis=1)
    output_csv_path = os.path.join(base_dir, 'results', f'pointcloud_{img_num}_with_material.csv')
    df.to_csv(output_csv_path, index=False)

    return {
        'labelmap': labelmap,
        'labels': labels,
        'result_image': os.path.join(base_dir, 'results', f"result_{img_num}.png"),
        'output_csv': output_csv_path
    }
    
# only for testing
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    img_num = '20250329_193301'
    point_path = os.path.join(base_dir, 'results', f'pointcloud_with_objects.csv')
    run_on_image_cpu(base_dir, img_num, point_path)
>>>>>>> upstream/master
