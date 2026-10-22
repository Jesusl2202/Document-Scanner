"""Transformaciones de imagen y retorno explícito a coordenadas originales."""
from PIL import Image, ImageOps, ImageFilter
import numpy as np

def otsu_threshold(gray):
    a=np.asarray(gray,dtype=np.uint8)
    hist=np.bincount(a.ravel(),minlength=256).astype(float)
    if np.count_nonzero(hist)<2:return gray.copy()
    prob=hist/hist.sum();weight=np.cumsum(prob);mean=np.cumsum(prob*np.arange(256));total=mean[-1]
    denominator=weight*(1-weight)
    variance=np.zeros(256)
    np.divide((total*weight-mean)**2,denominator,out=variance,where=denominator>0)
    threshold=int(np.argmax(variance))
    return Image.fromarray(np.where(a>threshold,255,0).astype(np.uint8))

def prepare_image(image,options):
    original=image.size
    method=options.get('preprocess','original')
    if method not in ('original','resize','otsu','illumination','denoise','blue_ink','local_binary'):raise ValueError('Preprocesamiento desconocido: '+method)
    im=image.convert('L' if options.get('grayscale',True) or method=='otsu' else 'RGB')
    if method=='blue_ink':
        # Intensificar tinta azul frente al papel; no asigna valores a los trazos.
        rgb=np.asarray(image.convert('RGB'),dtype=np.float32)
        strength=np.maximum(rgb[:,:,2]-rgb[:,:,0]-6,rgb[:,:,2]-rgb[:,:,1]-10)
        im=Image.fromarray((255-np.clip(strength*6,0,255)).astype(np.uint8))
    if method=='denoise':im=im.filter(ImageFilter.MedianFilter(size=3))
    if options.get('autocontrast',True):im=ImageOps.autocontrast(im)
    if method=='original':return im,{'original_size':original,'scale_x':1.,'scale_y':1.,'border':0,'method':method}
    # Mantener proporciones; reducir solo cuando se supera el presupuesto de píxeles.
    longest=max(original); target=int(options.get('target_long_edge',2200))
    scale=min(float(options.get('max_scale',3.)),max(1.,target/longest))
    width=max(1,round(original[0]*scale));height=max(1,round(original[1]*scale))
    border=int(options.get('border',20))
    budget=int(options.get('max_pixels',25000000))
    if border<0 or budget<(1+2*border)**2:
        raise ValueError('Borde inválido o presupuesto insuficiente para una imagen de 1 píxel')
    capped=(width+2*border)*(height+2*border)>budget
    if capped:
        # Buscar la mayor escala viable, incluyendo el borde. No descartar el documento.
        low,high=0.,scale
        for _ in range(64):
            mid=(low+high)/2
            mw=max(1,int(original[0]*mid));mh=max(1,int(original[1]*mid))
            if (mw+2*border)*(mh+2*border)<=budget:low=mid
            else:high=mid
        width=max(1,int(original[0]*low));height=max(1,int(original[1]*low))
    assert (width+2*border)*(height+2*border)<=budget
    if (width,height)!=original:im=im.resize((width,height),Image.Resampling.LANCZOS)
    if options.get('sharpen',False):im=im.filter(ImageFilter.UnsharpMask(radius=1,percent=120,threshold=3))
    if method=='illumination':
        # Corregir variación lenta de iluminación; preservar cajas y coordenadas.
        gray=im.convert('L')
        background=gray.filter(ImageFilter.GaussianBlur(radius=max(10,min(64,min(gray.size)/40))))
        a=np.asarray(gray,dtype=np.float32);b=np.asarray(background,dtype=np.float32)
        im=Image.fromarray(np.clip(a*230/np.maximum(b,1),0,255).astype(np.uint8))
    if method=='local_binary':im=local_binary(im.convert('L'),int(options.get('local_window',41)),float(options.get('local_k',.20)))
    if method=='otsu':im=otsu_threshold(im.convert('L'))
    im=ImageOps.expand(im,border=border,fill=255 if im.mode=='L' else (255,255,255))
    return im,{'original_size':original,'scale_x':width/original[0],'scale_y':height/original[1],'border':border,'method':method,'size_limited':capped,'output_size':im.size}

def original_box(box,transform):
    w,h=transform['original_size'];b=transform['border'];sx=transform['scale_x'];sy=transform['scale_y']
    return [max(0,min(w,(box[0]-b)/sx)),max(0,min(h,(box[1]-b)/sy)),
            max(0,min(w,(box[2]-b)/sx)),max(0,min(h,(box[3]-b)/sy))]


def local_binary(gray,window=41,k=.20):
    """Umbral local según media y desviación; no cambia escala ni geometría."""
    if window<3 or window%2==0 or not 0<k<1:raise ValueError('Ventana impar >=3 y k entre 0 y 1')
    a=np.asarray(gray.convert('L'),dtype=np.float64)
    pad=window//2
    def average(values):
        padded=np.pad(values,pad,mode='edge')
        integral=np.pad(padded,((1,0),(1,0)),mode='constant').cumsum(0).cumsum(1)
        return (integral[window:,window:]-integral[:-window,window:]-integral[window:,:-window]+integral[:-window,:-window])/(window*window)
    mean=average(a);variance=np.maximum(average(a*a)-mean*mean,0)
    threshold=mean*(1+k*(np.sqrt(variance)/128.-1))
    return Image.fromarray(np.where(a>threshold,255,0).astype(np.uint8))
