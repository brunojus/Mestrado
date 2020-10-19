
from preprocess import letterbox_image

from darknet import Darknet

from imutils.video import WebcamVideoStream,FPS

import numpy as np
import torch.nn as nn
from torch.autograd import Variable
import torch,cv2,random,os,time
import pickle as pkl
import argparse
import threading, queue
from torch.multiprocessing import Pool, Process, set_start_method
from util import write_results, load_classes
torch.multiprocessing.set_start_method('spawn')

def image_preparation(img, inp_dim):
  


    original_im = img
    dim = orig_im.shape[1], orig_im.shape[0]
    img = (letter_image(orig_im, (input_dim, input_dim)))
    img_ = img[:, :, ::-1].transpose((2, 0, 1)).copy()
    img_ = torch.from_numpy(original_im).float().div(255.0).unsqueeze(0)
    return img_, orig_im, dim

labels = {}
b_boxe = {}
def write(bboxes, img, classes, colors):

    x = b_boxes
    b_boxes = b_boxes[1:5]
    b_boxes = b_boxes.cpu().data.numpy()
    b_boxes = b_boxes.astype(int)
    b_boxes.update({"bbox":b_boxes.tolist()})
    
    b_boxes = torch.from_numpy(b_boxes)
    cls = int(x[-1])
    label = "{0}".format(classes[cls])
    labels.update({"Current Object":label})
    color = random.choice(colors)
    img = cv2.rectangle(img, (b_boxes[0],b_boxes[1]),(b_boxes[2],b_boxes[3]), color, 1)
    
    img = cv2.putText(img, label, (b_boxes[0]+2,b_boxes[3]+20), cv2.FONT_HERSHEY_PLAIN, 1, [225, 255, 255], 1)
    return img

class ObjectDetection:
    def __init__(self, id): 
        
        self.cap = cv2.VideoCapture(0)
        self.cap = WebcamVideoStream(src = id).start()
        self.cfgfile = "cfg/yolov3.cfg"
        
        self.weightsfile = "yolov3.weights"
        
        self.conf = float(0.5)
        self.nms_trhesh = round(0.4)
        self.amount_classes = 80
        self.classes = load_classes('data/coco.names')
        self.colors = pkl.load(open("pallete", "rb"))
        self.model = Darknet(self.cfgfile)
        self.CUDA = torch.cuda.is_available()
        self.model.load_weights(self.weightsfile)
        self.model.net_info["height"] = 160
        self.inp_dim = int(self.model.net_info["height"])
        self.width = 640 
        self.height = 480 
        print("Loading network.....")
        if self.CUDA:
            self.model.cuda()
        print("Network successfully loaded")
        assert self.inp_dim % 32 == 0
        assert self.inp_dim > 32
        self.model.eval()

    def main(self):
        q = queue.Queue()
        def frame_render(queue_from_cam):
            ret, frame = self.cap.read()
            frame = cv2.resize(frame,(self.wi, self.hei))
            queue_from_cam.put(frame)
        cam = threading.Thread(target=frame_render, args=(q,))
        cam.start()
        cam.join()
        frame = q.get()
        q.task_done()
        fps = FPS().start() 
        
        image, orig_image, dim = prep_image(frame, self.inp_dim)
        im_dim = torch.FloatTensor(dim).repeat(1,2)
        if self.CUDA:                            
            im_dim = im_dim.cuda()
            img = img.cuda()
        
        out_image = self.model(Variable(img), self.CUDA)
        out_image = write_results(output, self.confidence, self.num_classes, nms = True, nms_conf = self.nms_thesh)  
        output = output.type(torch.half)
        if list(output.size()) == [1,86]:
            #do nothing
        else:
            out_image[:,1:5] = torch.clamp(out_image[:,1:5], 0.0, float(self.inp_dim))/self.inp_dim
        

            out_image[:,[1,3]] *= frame.shape[1]
            out_image[:,[2,4]] *= frame.shape[0]
            list(map(lambda x: write(x, frame, self.classes, self.colors),out_image))

            x,y,w,h = b_boxes["b_box"][0],b_boxes["bbox"][1], b_boxes["bbox"][2], b_boxes["bbox"][3]
            dist = (2 * 3.14 * 180) / (w + h * 360)
            dist = round(distance * 2.54, 1)
            fb = ("{}".format(labels["Current Object"])+ " " +"is"+" at {} ".format(round(dist))+"cm")
            
            print(feedback)
            
            
            


        fps.update()
        fps.stop()
        print("[INFO] elasped time: {:.2f}".format(fps.elapsed()))
        print("[INFO] approx. FPS: {:.1f}".format(fps.fps()))
        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tostring()

