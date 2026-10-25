import pathlib
import numpy as np
import egm96

d = pathlib.Path(egm96.__file__).parent
npzs = list(d.rglob("*.npz"))
print("npz files:", npzs)
f = npzs[0]
a = np.load(f)
for k in a.files:
    arr = a[k]
    print(k, arr.dtype, arr.shape, "min", arr.min(), "max", arr.max())


def undulation(lat, lon):
    try:
        import egm96 as e
        return e.undulation(lat, lon)
    except Exception as ex:
        print("call err", ex)
        return None


print("undulation 48.14,11.58 =", undulation(48.14, 11.58))