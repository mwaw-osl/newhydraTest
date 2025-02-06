import sys,urllib,json
import base64
import requests
from PIL import Image
from math import cos,sin,pi
from multiprocessing import Pool
from io import BytesIO

"""
fname = sys.argv[1]
ra = float(sys.argv[2])
dec = float(sys.argv[3])
rot = float(sys.argv[4])
fov = float(sys.argv[5])
pincushion = float(sys.argv[6])
mode = int(sys.argv[7])
"""


def downloadData(url):
    try:
        resp = requests.get(url,stream=True)
        response = Image.open(resp.raw)
    except:
        response = None
    return response

def getPS1Image(ra,dec,rot,fov=0.99314,pincushion=77.6,npix=500,mode=0):
    baseURL = "https://alasky.cds.unistra.fr/hips-image-services/hips2fits?hips=CDS%2FP%2FPanSTARRS%2FDR1%2Fcolor-i-r-g&format=jpg&min_cut=0&max_cut=255"

    c = cos(rot*pi/-180)*fov/npix
    s = sin(rot*pi/-180)*fov/npix
    WCS = {"NAXIS1":npix,
           "NAXIS2":npix,
           "WCSAXES":2,
           "CRPIX1":npix/2,
           "CRPIX2":npix/2,
           "CD1_1":-1*c,
           "CD1_2":1*s,
           "CD2_1":-1*s,
           "CD2_2":-1*c,
           "CUNIT1":"deg",
           "CUNIT2":"deg",
           "CTYPE1":"RA---ZPN",
           "CTYPE2":"DEC--ZPN",
           "CRVAL1":ra,
           "CRVAL2":dec}

    WCS['PV2_1'] = 1.
    WCS['PV2_3'] = pincushion


    def makeURL(wcs):
        S = json.dumps(wcs)
        return baseURL+"&"+urllib.parse.urlencode({"wcs":S})


    def getMultipartImage(size):
        wcs = WCS.copy()
        urlList = []

        wcs['NAXIS1'] = size
        wcs['NAXIS2'] = size
        wcs['CD1_1'] *= npix/(size*3)
        wcs['CD1_2'] *= npix/(size*3)
        wcs['CD2_1'] *= npix/(size*3)
        wcs['CD2_2'] *= npix/(size*3)
        for crpix1 in [size+size//2,size//2,size//-2]:
            wcs['CRPIX1'] = crpix1
            for crpix2 in [size+size//2,size//2,size//-2]:
                wcs['CRPIX2'] = crpix2
                urlList.append(makeURL(wcs))

        with Pool(9) as P:
            images = P.map(downloadData,urlList)
        if None in images:
            return None
        img = Image.new('RGB',(size*3,size*3))
        imgCount = 0
        for dx in range(3):
            for dy in [2,1,0]:
                img.paste(images[imgCount],(dx*size,dy*size))
                imgCount += 1
        return img

    if mode==0:
        img = downloadData(makeURL(WCS))
    else:
        img = getMultipartImage(mode*npix)

    return img

    if fname is not None:
        tmp = BytesIO()
        img.save(tmp,'jpeg')
        tmp.seek(0)
        imageStr = base64.b64encode(tmp.read())
        f = open(fname,'w')
        f.write(imageStr.decode("utf-8"))
        f.close()
    return image

def getObjects(ra,dec,radius=1.,glimit=22,rlimit=22):
    from astroquery.mast import Catalogs
    coords = "{} {}".format(ra,dec)
    data = Catalogs.query_criteria(coordinates=coords,radius=radius,catalog="Panstarrs",release="dr2",table="stack",columns=["raStack","decStack"],gMeanApMag=[("lte",glimit)],rMeanApMag=[("lte",rlimit)],primaryDetection=1)
