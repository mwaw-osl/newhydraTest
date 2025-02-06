from math import pi,sin,cos,acos,asin,tan,atan2,sqrt,exp
import time

def DEG2RAD(deg):
    return deg*pi/180
def RAD2DEG(rad):
    return rad*180/pi


class Astrometry:
    A,B,guideA,guideB = 0.,0.,0.,0.
    def setABCoefficients(self,temp=20):
        wavelength = self.WAVELENGTH/10000.
        guideWave = self.GUIDEWAVELENGTH/10000.
        latitude = DEG2RAD(self.sitePars["KPNO_LAT"])

        self.A,self.B = refco(self.sitePars["KPNO_ALT"],temp+273.15,self.sitePars["KPNO_ATM_PRES"],self.sitePars["KPNO_HUMIDITY"],wavelength,latitude,self.sitePars["LAPSE_RATE"],self.sitePars["REFRACT_PREC"])

        self.guideA,self.guideB = refco(self.sitePars["KPNO_ALT"],temp+273.15,self.sitePars["KPNO_ATM_PRES"],self.sitePars["KPNO_HUMIDITY"],guideWave,latitude,self.sitePars["LAPSE_RATE"],self.sitePars["REFRACT_PREC"])

    def getRefractionOffsets(self,inRA,inDec,siderealTime,A,B):
        ra = inRA
        dec = inDec
        hourAngle = (siderealTime*15*pi/180)-inRA
        latitude = DEG2RAD(self.sitePars["KPNO_LAT"])
        cosLat = cos(latitude)
        sinLat = sin(latitude)

        cos_zdist = sin(dec)*sinLat+cos(dec)*cosLat*cos(hourAngle)
        airmass = 1./cos_zdist
        zdist = acos(cos_zdist)

        z_refract = refz(zdist,A,B)
        az = atan2(sin(hourAngle),cos(hourAngle)*sinLat-tan(dec)*cosLat)
        az += pi

        newDec = asin(sinLat*cos(z_refract)+cosLat*sin(z_refract)*cos(az))
        dDec = newDec-dec

        sinHa = -sin(az)*sin(z_refract)
        cosHa = (cos(z_refract)-sin(newDec)*sinLat)/cosLat
        newHa = atan2(sinHa,cosHa)
        dRA = hourAngle-newHa
        return dRA,dDec,airmass

    def refractCoords(self,ra,dec,cam=False):
        if cam:
            a,b = self.guideA,self.guideB
        else:
            a,b = self.A,self.B
        timeInterval = self.EXPTIME/self.sitePars["REFRACT_PTS"]
        startSideTime = self.LST-self.EXPTIME/2+timeInterval/2
        sumRA,sumDec,sumWeight = 0.,0.,0.
        for i in range(self.sitePars["REFRACT_PTS"]):
            obsSideTime = startSideTime+i*timeInterval
            dRA,dDec,airmass = self.getRefractionOffsets(ra,dec,obsSideTime,a,b)
            sumRA += dRA/airmass
            sumDec += dDec/airmass
            sumWeight += 1./airmass
        return ra+sumRA/sumWeight,dec+sumDec/sumWeight

    def rotatePoint(self,x,y):
        A = DEG2RAD(self.PA)-pi/2
        xout = x*sin(A)+y*cos(A)
        yout = -x*cos(A)+y*sin(A)
        return xout,yout

    def projectAndCorrect(self,ra,dec):
        arcsec2rad = pi/180./3600
        #from astropy.wcs import WCS
        #W = WCS({"CRVAL1":self.REFRA*180/pi,"CRVAL2":self.REFDEC*180/pi,"CD1_1":1,"CD1_2":0,"CD2_1":0,"CD2_2":1.,"CTYPE1":"RA---TAN","CTYPE2":"DEC--TAN"})
        X,Y = self.WCS.all_world2pix([ra*180/pi],[dec*180/pi],1)
        X = X[0]*pi/180
        Y = Y[0]*pi/180
        dist = 1.+self.sitePars["WIYN_PINCUSHION"]*(X*X+Y*Y)
        dist /= self.sitePars["WIYN_SCALE"]*arcsec2rad
        X *= dist
        Y *= dist
        return self.rotatePoint(X,Y)

    def skyToPlate(self,inRA,inDec):
        pra,pdec = inRA*pi/180,inDec*pi/180
        wra,wdec = self.refractCoords(pra,pdec,True)
        xcam,ycam = self.projectAndCorrect(wra,wdec)
        wra,wdec = self.refractCoords(pra,pdec)
        xspec,yspec = self.projectAndCorrect(wra,wdec)
        return xcam,ycam,xspec,yspec

    def plateToSky(self,x,y):
        angle = DEG2RAD(self.PA)
        rotC = cos(angle)*self.sitePars["WIYN_SCALE"]/3600.
        rotS = sin(angle)*self.sitePars["WIYN_SCALE"]/3600.
        cosDec = cos(self.FIELDDEC*pi/180)
        sinDec = sin(self.FIELDDEC*pi/180)

        xi = x*-rotC+y*-rotS
        eta = x*rotS+y*-rotC

        # Calculate the intermediate coordinates
        R = (xi**2+eta**2)**0.5
        phi = atan2(xi,-eta)

        # Determine theta from R(theta) (Eqn 68 from WCS paper II).
        # Solution can be found at:
        # https://www.wolframalpha.com/input?i=Solve%5Bx%2BC*x%5E3%3D%3DR%2Cx%5D
        C = self.sitePars["WIYN_PINCUSHION"]*(pi/180)**2
        rootTerm = (sqrt(3*(27*C*R*R+4)*C**3) + 9*R*C*C)**(1/3)
        nom = (2**(1/3))*rootTerm**2-2*C*3**(1/3)
        dom = (6**(2/3))*C*rootTerm
        theta = 90-nom/dom

        # Do the de-projection. See Eqn 2, Section 2.3 of WCS paper II
        #  (the -pi comes from the LONPOLE discussion in the previous section).
        sinPhi = sin(phi-pi)
        cosPhi = cos(phi-pi)
        sinTheta = sin(theta*pi/180)
        cosTheta = cos(theta*pi/180)
        arg1 = sinTheta*cosDec-cosTheta*sinDec*cosPhi
        arg2 = -1*cosTheta*sinPhi
        alpha = self.FIELDRA+atan2(arg2,arg1)*180/pi
        delta = asin(sinTheta*sinDec+cosTheta*cosDec*cosPhi)*180/pi
        return alpha,delta


RADIANS2DEGREES = 180./pi
DEG93_IN_RADIANS = 93/RADIANS2DEGREES
MOLAR_GAS_CONSTANT = 8314.32
DRY_AIR_MOL_WEIGHT = 28.9644
WATER_VAPOUR_MOL_WEIGHT = 18.0152
EARTH_RADIUS = 6378120.
DELTA = 18.36
TROPOPAUSE_HEIGHT = 11000.
RE_HEIGHT_LIMIT = 80000.
MAX_STRIPS = 16384

def drange(angle):
    result = angle%(2*pi)
    if abs(result)>=pi:
        result -= 2*pi*result/abs(result)
    return result

def atmt(r0,t0,alpha,gamm2,delm2,c1,c2,c3,c4,c5,c6,r):
    t = max(min(t0-alpha*(r-r0),320.),100.)
    tt0 = t/t0
    tt0gm2 = tt0**gamm2
    tt0dm2 = tt0**delm2
    dn = 1+(c1*tt0gm2-(c2-c5/t)*tt0dm2)*tt0
    rdndr = r*(-c3*tt0gm2 + (c4-c6/tt0)*tt0dm2)
    return t,dn,rdndr

def atms(rt,tt,dnt,gamal,r):
    b = gamal/tt
    w = (dnt-1)*exp(-b*(r-rt))
    return 1+w,-r*b*w

refraction_integrand = lambda dn,rdndr: rdndr/(dn+rdndr)

def refro(ozd,oh,atk,apm,arh,wl,phi,tlr,eps):
    zobs1 = drange(ozd)
    zobs2 = min(abs(zobs1),DEG93_IN_RADIANS)
    hm_ok = min(max(oh,-1e3),RE_HEIGHT_LIMIT)
    tdk_ok = min(max(atk,100.),500.)
    pmb_ok = min(max(apm,0.),1e4)
    rh_ok = min(max(arh,0.),1.)
    wl_ok = max(wl,0.1)
    alpha = min(max(abs(tlr),0.001),0.01)
    tolerance = min(max(abs(eps),1e-12),1.)/2.

    optic = wl_ok <=100.
    wl_squared = wl_ok*wl_ok
    gb = 9.784*(1.-0.0026*cos(phi+phi)-0.00000028*hm_ok)
    a = (287.6155+(1.62887+0.01360/wl_squared)/wl_squared)*273.15e-6/1013.25 if optic else 77.689e-6
    gamal = (gb*DRY_AIR_MOL_WEIGHT)/MOLAR_GAS_CONSTANT
    gamma = gamal/alpha
    gamm2 = gamma-2
    delm2 = DELTA-2
    tdc = tdk_ok-273.15
    psat = (1.+pmb_ok*(4.5e-6+6e-10*tdc*tdc))*10**((0.7859+0.03477*tdc)/(1+0.00412*tdc))
    pwo = 0 if pmb_ok<=0 else rh_ok*psat/(1.-(1-rh_ok)*psat/pmb_ok)
    w = pwo*(1-WATER_VAPOUR_MOL_WEIGHT/DRY_AIR_MOL_WEIGHT)*gamma/(DELTA-gamma)
    c1 = a*(pmb_ok+w)/tdk_ok
    c2 = (a*w+(4.8746e-6*optic+6.3938e-6)*pwo)/tdk_ok
    c3 = (gamma-1)*alpha*c1/tdk_ok
    c4 = (DELTA-1.)*alpha*c2/tdk_ok
    c5 = 0 if optic else 375463e-6*pwo/tdk_ok
    c6 = 0 if optic else c5*delm2*alpha/(tdk_ok*tdk_ok)

    r0 = EARTH_RADIUS+hm_ok
    temp0,dn0,rdndr0 = atmt(r0,tdk_ok,alpha,gamm2,delm2,c1,c2,c3,c4,c5,c6,r0)
    sk0 = dn0*r0*sin(zobs2)
    f0 = refraction_integrand(dn0,rdndr0)

    rt = EARTH_RADIUS + max(TROPOPAUSE_HEIGHT,hm_ok)
    tt,dnt,rdndrt = atmt(r0,tdk_ok,alpha,gamm2,delm2,c1,c2,c3,c4,c5,c6,rt)
    sine = sk0/(rt*dnt)
    zt = atan2(sine,sqrt(max(1-sine*sine,0)))
    ft = refraction_integrand(dnt,rdndrt)

    dnts,rdndrp = atms(rt,tt,dnt,gamal,rt)
    sine = sk0/(rt*dnts)
    zts = atan2(sine,sqrt(max(1-sine*sine,0)))
    fts = refraction_integrand(dnts,rdndrp)

    rs = EARTH_RADIUS+RE_HEIGHT_LIMIT
    dns,rdndrs = atms(rt,tt,dnt,gamal,rs)
    sine = sk0/(rs*dns)
    zs = atan2(sine,sqrt(max(1-sine*sine,0)))
    fs = refraction_integrand(dns,rdndrs)

    refp,reft = 0.,0.
    for k in [0,1]:
        ref_old = 1.
        num_strips = 8
        if k==0:
            z0 = zobs2
            z_range = zt-z0
            fb = f0
            ff = ft
        else:
            z0 = zts
            z_range = zs-z0
            fb = fts
            ff = fs
        f_odd,f_even = 0.,0.
        step = 1
        while 1:
            h = z_range/num_strips
            r = r0 if k==0 else rt
            for i in range(1,num_strips,step):
                sine_zd = sin(z0+h*i)
                if sine_zd>1e-20:
                    ww = sk0/sine_zd
                    rg = r
                    dr = 1e6
                    for j in range(4):
                        if abs(dr)<=1:
                            break
                        if k==0:
                            tg,dn,rdndr = atmt(r0,tdk_ok,alpha,gamm2,delm2,c1,c2,c3,c4,c5,c6,rg)
                        else:
                            dn,rdndr = atms(rt,tt,dnt,gamal,rg)
                        dr = (rg*dn-ww)/(dn+rdndr)
                        rg = rg-dr
                    r = rg
                if k==0:
                    t,dn,rdndr = atmt(r0,tdk_ok,alpha,gamm2,delm2,c1,c2,c3,c4,c5,c6,r)
                else:
                    dn,rdndr = atms(rt,tt,dnt,gamal,r)
                f = refraction_integrand(dn,rdndr)
                if step==1 and i%2==0:
                    f_even += f
                else:
                    f_odd += f
            refp = h*(fb+4*f_odd+2*f_even+ff)/3.
            if abs(refp-ref_old)>tolerance and num_strips<MAX_STRIPS:
                ref_old = refp
                num_strips += num_strips
                f_even = f_even+f_odd
                f_odd = 0.
                step = 2
            else:
                if k==0:
                    reft = refp
                break
    result = reft+refp
    if zobs1<0:
        result *= -1
    return result

def refco(oh,atk,apm,arh,wl,phi,tlr,eps):
    ATAN_1 = 0.7853981633974483
    ATAN_4 = 1.325817663668033

    r1 = refro(ATAN_1, oh, atk, apm, arh, wl, phi, tlr, eps)
    r2 = refro(ATAN_4, oh, atk, apm, arh, wl, phi, tlr, eps)
    refa = (64*r1-r2)/60
    refb = (r2-4*r1)/60
    return refa,refb

C1,C2,C3,C4,C5 = 0.55445,-0.01133,0.00202,0.28385,0.02390
ZD_THRESHOLD83 = 83./RADIANS2DEGREES
REF83 = (C1 + C2*7.0 + C3*49.0) / (1.0 + C4*7.0 + C5*49.0)
def refz(zu,refa,refb):
    zu1 = min(zu,ZD_THRESHOLD83)
    zl = zu1
    sine = sin(zl)
    cosine = cos(zl)
    tangent = sine/cosine
    tangent_sqr = tangent*tangent
    tangent_cube = tangent*tangent_sqr
    zl = zl-(refa*tangent + refb*tangent_cube)/(1.+(refa+3*refb*tangent_sqr)/(cosine*cosine))

    sine = sin(zl)
    cosine = cos(zl)
    tangent = sine/cosine
    tangent_sqr = tangent*tangent
    tangent_cube = tangent*tangent_sqr
    ref = zu1-zl+(zl-zu1+refa*tangent+refb*tangent_cube)/(1+(refa+3*refb*tangent_sqr)/(cosine*cosine))
    if zu>zu1:
        E = 90.-min(DEG93_IN_RADIANS,zu*RADIANS2DEGREES)
        E2 = E*E
        ref = (ref/REF83)*(C1+C2*E+C3*E2)/(1+C4*E+C5*E2)
    return zu-ref

