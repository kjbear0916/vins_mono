#!/usr/bin/env python3
import cv2, numpy as np
img = cv2.imread("/tmp/nadir_frame.png")
print("shape", img.shape, "mean", img.mean(), img.std())
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_7X7_1000)
params = cv2.aruco.DetectorParameters()
det = cv2.aruco.ArucoDetector(aruco_dict, params)
corners, ids, rej = det.detectMarkers(img)
print("detected ids:", ids.flatten().tolist() if ids is not None else None)
print("rejected candidates:", len(rej))
hfov_x = 82.9*(np.pi/180)
# yaw-less; just print where brightness is
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
print("gray stats: min", gray.min(), "max", gray.max(), "mean", gray.mean())
print("unique-ish values")
hist = np.histogram(gray, bins=16)[0]
print(hist)
cv2.imwrite("/tmp/nadir_annot.png", cv2.aruco.drawDetectedMarkers(img.copy(), corners, ids))
print("saved /tmp/nadir_annot.png")