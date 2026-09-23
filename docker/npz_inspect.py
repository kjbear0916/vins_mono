import zipfile
import numpy as np

with zipfile.ZipFile("/tmp/egm96.whl") as z:
    z.extract("egm96/data/egm96-5.npz", "/tmp/egm96_extract")

a = np.load("/tmp/egm96_extract/egm96/data/egm96-5.npz")
for k in a.files:
    arr = a[k]
    print(k, arr.dtype, arr.shape, "min", arr.min(), "max", arr.max(), "flat nz sample:", arr.ravel()[:5])
print("size bytes:", sum(a[k].nbytes for k in a.files))