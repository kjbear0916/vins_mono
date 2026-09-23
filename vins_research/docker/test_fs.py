import cv2

for p in [
    "/root/catkin_ws/src/VINS-Mono/config/euroc/euroc_config.yaml",
    "/root/catkin_ws/src/VINS-Mono/config/simulation/simulation_config.yaml",
    "/root/catkin_ws/src/vins_research/config/sim_config.yaml",
]:
    fs = cv2.FileStorage(p, cv2.FILE_STORAGE_READ)
    print(p, "opened:", fs.isOpened())
    if fs.isOpened():
        print("  comment_type:", fs.getNode("comment").isString())
        print("  keys sample:", list(fs.root().keys())) if hasattr(fs.root(), "keys") else None
    fs.release()