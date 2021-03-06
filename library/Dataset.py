import cv2
import numpy as np
import os
from File import *

"""
Will hold all the ImageData objbects. Should only be used when evaluating or
training. When running, pass image and array of 2d boxes directly into an ImageData
object
"""
class Dataset:
    def __init__(self, path):
        self.data = {}

        top_label_path = path + "/label"
        top_img_path = path + "/image"
        top_calib_path = path + "/calib"

        K = self.get_K(os.path.abspath(os.path.dirname(os.path.dirname(__file__)) + '/camera_cal/calib_cam_to_cam.txt'))
        self.ids = [x.split('.')[0] for x in sorted(os.listdir(top_img_path))]


        for id in self.ids:
            self.data[id] = {}
            img_path = top_img_path + '/%s.png'%id
            img = cv2.imread(img_path)
            self.data[id]['Image'] = img

            calib_path = top_calib_path + '/%s.txt'%id
            self.data[id]['Calib'] = get_calibration_cam_to_image(calib_path)


            label_path = top_label_path + '/%s.txt'%id
            labels = self.parse_label(label_path)
            objects = []
            for label in labels:
                box_2d = label['Box_2D']
                objects.append(DetectedObject(img, box_2d, K, label=label))

            self.data[id]['Objects'] = objects

        self.current = 0


    def parse_label(self, label_path):
        buf = []
        with open(label_path, 'r') as f:
            for line in f:
                line = line[:-1].split(' ')

                Class = line[0]
                if Class == "DontCare":
                    continue

                for i in range(1, len(line)):
                    line[i] = float(line[i])

                Alpha = line[3] # what we will be regressing
                Ry = line[14]
                top_left = (int(round(line[4])), int(round(line[5])))
                bottom_right = (int(round(line[6])), int(round(line[7])))
                Box_2D = [top_left, bottom_right]

                Dimension = [line[8], line[9], line[10]] # height, width, length
                Location = [line[11], line[12], line[13]] # x, y, z
                Location[1] -= Dimension[0] / 2 # bring the KITTI center up to the middle of the object

                buf.append({
                        'Class': Class,
                        'Box_2D': Box_2D,
                        'Dimensions': Dimension,
                        'Location': Location,
                        'Alpha': Alpha,
                        'Ry': Ry
                    })
        return buf


    def get_K(self, cab_f):
        for line in open(cab_f, 'r'):
            if 'K_02' in line:
                cam_K = line.strip().split(' ')
                cam_K = np.asarray([float(cam_K) for cam_K in cam_K[1:]])
                return_matrix = np.zeros((3,4))
                return_matrix[:,:-1] = cam_K.reshape((3,3))

        return return_matrix



    def __iter__(self):
        return self

    def next(self):
        if self.current  == len(self.ids):
            raise StopIteration
        else:
            self.current += 1
            id = self.ids[self.current-1]
            return self.data[id]


class DetectedObject:
    def __init__(self, img, box_2d, K, label=None):
        self.theta_ray = self.calc_theta_ray(img, box_2d, K)
        self.img = self.format_img(img, box_2d)
        self.label = label


    def calc_theta_ray(self, img, box_2d, K):
        width = img.shape[1]
        fovx = 2 * np.arctan(width / (2 * K[0][0]))
        center = (box_2d[1][0] + box_2d[0][0]) / 2
        dx = center - (width / 2)

        mult = 1
        if dx < 0:
            mult = -1
        dx = abs(dx)
        angle = np.arctan( (2*dx*np.tan(fovx/2)) / width )
        angle = angle * mult

        return angle

    def format_img(self, img, box_2d):

        img=img.astype(np.float) / 255

        img[:, :, 0] = (img[:, :, 0] - 0.406) / 0.225
        img[:, :, 1] = (img[:, :, 1] - 0.456) / 0.224
        img[:, :, 2] = (img[:, :, 2] - 0.485) / 0.229

        # crop image
        batch = np.zeros([1, 3, 224, 224], np.float)
        pt1 = box_2d[0]
        pt2 = box_2d[1]
        crop = img[pt1[1]:pt2[1]+1, pt1[0]:pt2[0]+1]
        crop = cv2.resize(src = crop, dsize=(224, 224), interpolation=cv2.INTER_CUBIC)

        # cv2.imshow('hello', crop) # to see the input cropped section
        # cv2.waitKey(0)

        # recolor, reformat
        batch[0, 0, :, :] = crop[:, :, 2]
        batch[0, 1, :, :] = crop[:, :, 1]
        batch[0, 2, :, :] = crop[:, :, 0]

        return batch
