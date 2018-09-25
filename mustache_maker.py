# USAGE:
#   docker run -it --rm -e ./.env -e DISPLAY=$DISPLAY -v `pwd`:/data dymat/opencv python /data/mustache_maker.py
# reference: https://sublimerobots.com/2015/02/dancing-mustaches/
#####################################################################

import cv2, random, os
import numpy as np

def resize(im, target_size, max_size):
    """
    only resize input image to target size and return scale
    :param im: BGR image input by opencv
    :param target_size: one dimensional size (the short side)
    :param max_size: one dimensional max size (the long side)
    :return:
    """
    im_shape = im.shape
    im_size_min = np.min(im_shape[0:2])
    im_size_max = np.max(im_shape[0:2])
    im_scale = float(target_size) / float(im_size_min)
    if np.round(im_scale * im_size_max) > max_size:
        im_scale = float(max_size) / float(im_size_max)
    im = cv2.resize(im, None, None, fx=im_scale, fy=im_scale, interpolation=cv2.INTER_LINEAR)
    return im, im_scale

def select_mustache_overlay():
    #-----------------------------------------------------------------------------
    #       Load and configure mustache (.png with alpha transparency)
    #-----------------------------------------------------------------------------
    global origMustacheHeight, origMustacheWidth, imgMustache, orig_mask_inv, orig_mask
    # Randomly pick a mustache from the overlay directory:
    random_filename = random.choice([
        x for x in os.listdir(baseDataPath + "overlay/")
        if os.path.isfile(os.path.join(baseDataPath + "overlay/", x))
    ])
    print(random_filename)

    # Load our overlay image: mustache.png
    imgMustache = cv2.imread(baseDataPath + "overlay/" + random_filename, -1)

    # Create the mask for the mustache
    orig_mask = imgMustache[:,:,3]

    # Create the inverted mask for the mustache
    orig_mask_inv = cv2.bitwise_not(orig_mask)

    # Convert mustache image to BGR
    # and save the original image size (used later when re-sizing the image)
    imgMustache = imgMustache[:,:,0:3]
    origMustacheHeight, origMustacheWidth = imgMustache.shape[:2]


#-----------------------------------------------------------------------------
#       Main program loop
#-----------------------------------------------------------------------------
def main():
    global baseDataPath
    # location of OpenCV Haar Cascade Classifiers:
    baseDataPath = "/root/stashorizer/"

    # xml files describing our haar cascade classifiers
    faceCascadeFilePath = baseDataPath + "haarcascade_frontalface_default.xml"
    noseCascadeFilePath = baseDataPath + "haarcascade_mcs_nose.xml"

    # build our cv2 Cascade Classifiers
    faceCascade = cv2.CascadeClassifier(faceCascadeFilePath)
    noseCascade = cv2.CascadeClassifier(noseCascadeFilePath)

    print("opening image " + baseDataPath + "image_raw.jpg")
    frame = cv2.imread(baseDataPath + "image_raw.jpg", -1)
    frame, scale = resize(frame.copy(), 600, 1000)

    # Create greyscale image from the video feed
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces in input video stream
    faces = faceCascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE
    )

    # Iterate over each face found
    for (x, y, w, h) in faces:

        # randomly select mustache mask from overlay directory
        select_mustache_overlay()

        # Un-comment the next line for debug (draw box around all faces)
        # face = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)

        roi_gray = gray[y:y+h, x:x+w]
        roi_color = frame[y:y+h, x:x+w]

        # Detect a nose within the region bounded by each face (the ROI)
        nose = noseCascade.detectMultiScale(roi_gray)

        for (nx,ny,nw,nh) in nose:
            # Un-comment the next line for debug (draw box around the nose)
            #cv2.rectangle(roi_color,(nx,ny),(nx+nw,ny+nh),(255,0,0),2)

            # The mustache should be three times the width of the nose
            mustacheWidth =  3 * nw
            mustacheHeight = mustacheWidth * origMustacheHeight / origMustacheWidth

            # Center the mustache on the bottom of the nose
            x1 = nx - (mustacheWidth/4)
            x2 = nx + nw + (mustacheWidth/4)
            y1 = ny + nh - (mustacheHeight/2)
            y2 = ny + nh + (mustacheHeight/2)

            # Check for clipping
            if x1 < 0:
                x1 = 0
            if y1 < 0:
                y1 = 0
            if x2 > w:
                x2 = w
            if y2 > h:
                y2 = h

            # Re-calculate the width and height of the mustache image
            mustacheWidth = x2 - x1
            mustacheHeight = y2 - y1

            # Re-size the original image and the masks to the mustache sizes
            # calcualted above
            mustache = cv2.resize(imgMustache, (mustacheWidth,mustacheHeight), interpolation = cv2.INTER_AREA)
            mask = cv2.resize(orig_mask, (mustacheWidth,mustacheHeight), interpolation = cv2.INTER_AREA)
            mask_inv = cv2.resize(orig_mask_inv, (mustacheWidth,mustacheHeight), interpolation = cv2.INTER_AREA)

            # take ROI for mustache from background equal to size of mustache image
            roi = roi_color[y1:y2, x1:x2]

            # roi_bg contains the original image only where the mustache is not
            # in the region that is the size of the mustache.
            roi_bg = cv2.bitwise_and(roi,roi,mask = mask_inv)

            # roi_fg contains the image of the mustache only where the mustache is
            roi_fg = cv2.bitwise_and(mustache,mustache,mask = mask)

            # join the roi_bg and roi_fg
            dst = cv2.add(roi_bg,roi_fg)

            # place the joined image, saved to dst back over the original image
            roi_color[y1:y2, x1:x2] = dst

            break

    # Display the resulting frame
    print("Detected " + str(len(faces)) + " faces")
    if (len(faces) > 0):
        cv2.imwrite(baseDataPath + "image_annotated.jpg", frame)

if __name__ == '__main__':
    try:
        main()
    except:
        raise