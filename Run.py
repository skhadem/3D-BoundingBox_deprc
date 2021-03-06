"""
Big Picture:
- use a 2D box of an object in scene (can get it from label or yolo eventually)
- pass image cropped to object through the model
- net outputs dimension and oreintation, then calculate the location (T) using camera
    cal and lots of math
- put the calculated 3d location onto 2d image using plot_regressed_3d_bbox
- visualize
Plan:
[x] reformat data structure to understand it better
[x] use purely truth values from label for dimension and orient to test math
[ ] regress dimension and orient from net
[ ] use yolo or rcnn to get the 2d box and class, so run from just an image (and cal)
[ ] Try and optimize to be able to run on video
[ ] Ros node eventually
Random TODOs:
[ ] loops inside of plotting functions
[x] Move alot of functions to a library and import it
Notes:
- The net outputs an angle (actually a sin and cos) relative to an angle defined
    by the # of bins, thus the # of bins used to train model should be known
- Everything should be using radians, just for consistancy (old version used degrees, so careful!)
- Is class ever used? Could this be an improvement?
"""


from library.Dataset import *
from library.Math import *
from library.Plotting import *
from Library import Model

import os
import cv2

import torch
import torch.nn as nn
from torch.autograd import Variable
from torchvision.models import vgg as V


debug_corners = True

# plot from net output. The orient should be global
# after done testing math, can remove label param
def plot_regressed_3d_bbox(img, truth_img, box_2d, dimensions, alpha, theta_ray, cam_to_img, label):

    # use truth for now
    truth_dims = label['Dimensions']
    truth_orient = label['Ry']

    # the math! returns X, the corners used for constraint
    center, X = calc_location(dimensions, cam_to_img, box_2d, alpha, theta_ray)

    center = [center[0][0], center[1][0], center[2][0]]

    truth_pose = label['Location']

    print "Estimated pose:"
    print center
    print "Truth pose:"
    print truth_pose
    print "-------------"

    plot_2d_box(truth_img, box_2d)
    plot_3d_box(img, cam_to_img, truth_orient, truth_dims, center) # 3d boxes

    if debug_corners:
        # plot the corners that were used
        # these corners returned are the ones that are unrotated, because they were
        # in the calculation. We must find the indicies of the corners used, then generate
        # the roated corners and visualize those
        left = X[0]
        right = X[1]
        # DEBUG with left and right as different colors
        # corners = create_corners(truth_dims) # unrotated
        corners = create_corners(dimensions) # unrotated

        left_corner_indexes = [corners.index(i) for i in left] # get indexes
        right_corner_indexes = [corners.index(i) for i in right] # get indexes

        # get the rotated version
        R = rotation_matrix(truth_orient)
        # corners = create_corners(truth_dims, location=center, R=R)
        # corners_used = [corners[i] for i in corner_indexes]
        #
        # # plot
        # plot_3d_pts(img, corners_used, truth_pose, cam_to_img=cam_to_img, relative=False)

        corners = create_corners(truth_dims, location=truth_pose, R=R)
        left_corners_used = [corners[i] for i in left_corner_indexes]
        right_corners_used = [corners[i] for i in right_corner_indexes]

        # plot
        for i, pt in enumerate(left_corners_used):
            plot_3d_pts(truth_img, [pt], truth_pose, cam_to_img=cam_to_img, relative=False, constraint_idx=0)

        for i, pt in enumerate(right_corners_used):
            plot_3d_pts(truth_img, [pt], truth_pose, cam_to_img=cam_to_img, relative=False, constraint_idx=2)

        plot_3d_box(truth_img, cam_to_img, truth_orient, truth_dims, truth_pose) # 3d boxes




def main():

    store_path = os.path.abspath(os.path.dirname(__file__)) + '/models'
    model_lst = [x for x in sorted(os.listdir(store_path)) if x.endswith('.pkl')]
    if len(model_lst) == 0:
        print 'No previous model found, please check it'
        exit()
    else:
        print 'Find previous model %s'%model_lst[-1]
        vgg = V.vgg19_bn(pretrained=False)
        model = Model.Model(features=vgg.features, bins=2).cuda()
        params = torch.load(store_path + '/%s'%model_lst[-1])
        model.load_state_dict(params)
        model.eval()

    dataset = Dataset(os.path.abspath(os.path.dirname(__file__)) + '/eval')

    bins = model.bins
    centerAngle = np.zeros(bins)
    interval = 2 * np.pi / bins
    for i in range(1, bins):
        centerAngle[i] = i*interval


    for data in dataset:
        truth_img = data['Image']
        img = np.copy(truth_img)
        objects = data['Objects']
        cam_to_img = data['Calib']

        for object in objects:
            label = object.label
            theta_ray = object.theta_ray
            batch = object.img

            alpha = label['Alpha']
            dimensions = label['Dimensions']

            batch = Variable(torch.FloatTensor(batch), requires_grad=False).cuda()
            [orient, conf, dim] = model(batch)
            orient = orient.cpu().data.numpy()[0, :, :]
            conf = conf.cpu().data.numpy()[0, :]
            dim = dim.cpu().data.numpy()[0, :]
            argmax = np.argmax(conf)

            orient = orient[argmax, :]
            cos = orient[0]
            sin = orient[1]
            theta = np.arctan2(sin, cos)
            theta = theta + centerAngle[argmax]

            print theta
            print alpha

            exit()




            plot_regressed_3d_bbox(img, truth_img, label['Box_2D'], dim, alpha, theta_ray, cam_to_img, label)

        numpy_vertical = np.concatenate((truth_img, img), axis=0)
        cv2.imshow('2D detection on top, 3D prediction on bottom', numpy_vertical)
        cv2.waitKey(0)





if __name__ == '__main__':
    main()
