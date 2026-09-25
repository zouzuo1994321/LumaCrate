import os
from PySide6.QtGui import QImage
D = r"C:/Users/zouzu/AppData/Local/Temp/lmc_v1300/dev/screenshots_v1300_live"
def load(n): return QImage(os.path.join(D,n))
def dr(a,b,step=4,x0=200,y0=70):
    ia,ib=(a if isinstance(a,QImage) else a.toImage()),(b if isinstance(b,QImage) else b.toImage()); h=min(ia.height(),ib.height())-10; w=min(ia.width(),ib.width())-40
    tot=n=0
    for y in range(y0,h,step):
        for x in range(x0,w,step):
            pa=ia.pixelColor(x,y); pb=ib.pixelColor(x,y); tot+=1
            if abs(pa.red()-pb.red())+abs(pa.green()-pb.green())+abs(pa.blue()-pb.blue())>12: n+=1
    return n*100.0/max(1,tot)
base = load("91_live_actors_az.png")
for n in ("92a_live_actors_jump_C.png","92d_live_actors_jump_C.png","97_live_actors_jump_Z.png","93_live_directors_az.png"):
    print("%-32s vs 91: 变化 %5.1f%%" % (n, dr(base, load(n))))
print("%-32s vs 92d: 变化 %5.1f%%" % ("97_live_actors_jump_Z.png", dr(load("92d_live_actors_jump_C.png"), load("97_live_actors_jump_Z.png"))))
