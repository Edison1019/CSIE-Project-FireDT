# Material Estimation
This is an unofficial implementation of this [paper](http://labelmaterial.s3.amazonaws.com/release/cvpr2015-minc.pdf) for material estimation. The authors has provided their model weights in Caffe while not the code for inference(which requires denseCRF for post processing). 

This repo provides codes to convert their original Caffe model to PyTorch, and re-implement three key components mentioned in the paper:
  - DenseCRF
  - Shift-Pooling(refer to this [paper](https://arxiv.org/abs/1312.6229) for more details)
  - LRN(local response normalization in Googlenet). 
  
Note that the denseCRF used here is RGB based and the hyper-parameters are arbitrarily copied from this [repo](https://github.com/kazuto1011/deeplab-pytorch). Please check [here](https://www.philkr.net/code/) if you want to use the denseCRF mentioned in the paper

## Requirement
- [pydensecrf](https://github.com/lucasb-eyer/pydensecrf)
- [pytorch](https://pytorch.org/)
- opencv

## Model Convertion
Please use this [repo](https://github.com/vadimkantorov/caffemodel2pytorch) to convert the Caffe model to PyTorch. After the convertion, remember to squeeze the dimension of bias(from (1,1,1,K) -> (K)) and convert the fully connected layers to convolutional layers. Code example:

```
# Assuming that fc6.weight.size() == (1,1,4096,25088)
f['conv_fc6.weight'] = f['fc6.weight'].squeeze().view(4096,512,7,7)
f['conv_fc6.bias'] = f['fc6.bias'].squeeze()
```

An example of Googlenet after conversion is [provided](https://github.com/dulucas/material_prediction_pytorch/tree/main/weights). Note that the Alexnet provided by the authors is not usable.

## Examples
Images captures from [minc dataset](http://opensurfaces.cs.cornell.edu/publications/minc/) and [Ycb dataset](https://www.ycbbenchmarks.com/)
| RGB Input | Material Segmentation |
| ------------- | ------------- |
| ![Material Estimation](./examples/RGB_ycb.png)  | ![Material Estimation](./examples/Material_ycb.png)  |
| ![Material Estimation](./examples/RGB_minc.png)  | ![Material Estimation](./examples/Material_minc.png)  |

## Citation
```bash
@inproceedings{bell2015material,
  title={Material recognition in the wild with the materials in context database},
  author={Bell, Sean and Upchurch, Paul and Snavely, Noah and Bala, Kavita},
  booktitle={Proceedings of the IEEE conference on computer vision and pattern recognition},
  pages={3479--3487},
  year={2015}
}
```

## Contact and Contribution
Feel free to contact me dulucas24@gmail.com, any contribution is welcome.
