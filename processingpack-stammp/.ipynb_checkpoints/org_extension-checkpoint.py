from copy import deepcopy

import numpy as np
import skimage
from skimage import measure
import pandas as pd
import matplotlib.pyplot as pl

import experiment as exp
import chipcollections as collections


INTRA_TILE_SPACING = 63

def calculateRotation(ul, ur):
    """
    
    
    """
    vec = np.array(ur)-np.array(ul)
    dotProd = np.dot([1, 0], vec)
    length = np.linalg.norm(vec)

    rotation = -np.degrees(np.arccos(dotProd / length))
    return rotation


def coordTransform(sourceImgShape, rotImgShape, xy, rot):
    """
    
    
    """
    coord = np.array(xy)
    org_center = (np.array(sourceImgShape[:2][::-1])-1)/2.
    rot_center = (np.array(rotImgShape[:2][::-1])-1)/2.
    org = xy-org_center
    a = np.deg2rad(rot)
    new = np.array([org[0]*np.cos(a) + org[1]*np.sin(a),
            -org[0]*np.sin(a) + org[1]*np.cos(a) ])
    return tuple((new+rot_center).astype(int))


def rotateImage(imgdata, org_corners):
    """
    
    
    """
    rotation = calculateRotation(org_corners.ul, org_corners.ur)
    rot_img = skimage.transform.rotate(imgdata, rotation, resize = True, preserve_range = True)
    return rot_img


def transformCorners(imgdata, rotimgdata, oc):
    """
    
    
    """
    org_corners = exp.Device._corners(oc) 
    rotation = calculateRotation(org_corners.ul, org_corners.ur)
    rotCorners = tuple([coordTransform(imgdata.shape, rotimgdata.shape, xy, rotation) for xy in org_corners])
    rot_corners = exp.Device._corners(rotCorners) 
    return rot_corners


def splitEdge(corners, num_arrs, x):
    """
    
    
    """
    if num_arrs == 0:
        return []
    elif num_arrs ==1:
        return [corners]
    else:
        global INTRA_TILE_SPACING
        def getVector(c1, c2, n):
            vec = c1-c2
            v = np.array(vec)
            edgeLen = np.linalg.norm(vec)
            unit_v = v/edgeLen
            segment = unit_v*n
            return segment
        c1, c2 = corners
        top = [c1, c1+getVector(c2, c1, x)]
        bottom = [c2+getVector(c1, c2, x), c2]
        
        newTop = top[1]+getVector(top[1], top[0], INTRA_TILE_SPACING)
        newbottom = bottom[0]+getVector(bottom[0], bottom[1], INTRA_TILE_SPACING)
        
        inbetween = splitEdge(deepcopy(np.array([newTop, newbottom])), deepcopy(num_arrs) - 2, x)
        return [top, *inbetween, bottom]


def getArrayPoints(edgeVertices, num_arrs):
    """
    
    
    """
    splitEdge_Corners = np.array(edgeVertices)
    global INTRA_TILE_SPACING

    vec = splitEdge_Corners[0] - splitEdge_Corners[1]
    v = np.array(vec)
    edgeLen = np.linalg.norm(vec)

    x = (edgeLen - ((num_arrs-1)*INTRA_TILE_SPACING)) / num_arrs
    points = splitEdge(splitEdge_Corners, num_arrs, x)
    return points


def getPartitions(rot_corners, subarray_dims):
    """
    
    
    """
    ul, ur, ll, lr = rot_corners
    numcols, numrows = subarray_dims
    top, bottom, left, right = ((ul, ur),
                            (ll, lr),
                            (ul, ll),
                            (ur, lr)
                           )
    flatten = lambda f: [item for sublist in f for item in sublist]
    verticalLines = np.array([flatten(getArrayPoints(top, numcols)), flatten(getArrayPoints(bottom, numcols))], dtype = int)
    horizontalLines = np.array([flatten(getArrayPoints(left, numrows)), flatten(getArrayPoints(right, numrows))], dtype = int)

    verticalLines_t = list(zip(verticalLines[0], verticalLines[1]))
    horizontalLines_t = list(zip(horizontalLines[0], horizontalLines[1]))
    
    return (verticalLines_t, horizontalLines_t)


##########################################################################################
def readTiff(handle):
    """
    
    
    """
    with skimage.external.tifffile.TiffFile(str(handle)) as tif:
        data = tif.asarray()
    return data


def readAndRotateImg(srcHandle, oc, subarray_dims, targetHandle = None):
    """
    
    
    """
    srcImg = readTiff(srcHandle)
    org_corners = exp.Device._corners(oc)
    rot_img = rotateImage(srcImg, org_corners)
    if targetHandle:
        skimage.external.tifffile.imsave(str(targetHandle), rot_img)
    return rot_img



##########################################################################################

def getCorners(index, horizontalLines_t, verticalLines_t):
    """
    
    
    """
    col, row = index
    ctop, cbottom = (horizontalLines_t[row*2], horizontalLines_t[row*2+1])
    cleft, cright = (verticalLines_t[col*2], verticalLines_t[col*2+1])


    def getIntersection(segment1, segment2):
        A = np.array(segment1)
        B = np.array(segment2)
        t, s = np.linalg.solve(np.array([A[1]-A[0], B[0]-B[1]]).T, B[0]-A[0])
        return ((1-t)*A[0] + t*A[1]).astype(int)

    c_ul = tuple(getIntersection(ctop, cleft))
    c_ur = tuple(getIntersection(ctop, cright))
    c_ll = tuple(getIntersection(cbottom, cleft))
    c_lr = tuple(getIntersection(cbottom, cright))
    
    return (c_ul, c_ur, c_ll, c_lr)

def showWell(chamberObject, arrayIDs, vmin = None, vmax = None, cmap = 'viridis_r'):
    """
    
    
    """
    pl.imshow(chamberObject.data, vmin = vmin, vmax = vmax, cmap = cmap)
    pl.colorbar()
    title = '{}.{}.{}'.format(str(arrayIDs['chamber']), str(arrayIDs['array']), str(arrayIDs['time']))
    pl.title('{} | {}'.format(title, str(chamberObject.index)))
    pl.axis('off')
    pl.show()

def showContours(data, level):
    """
    
    
    """
    r = data
    # Find contours at a constant value of 0.8
    contours = measure.find_contours(r, level)

    # Display the image and plot all contours found
    pl.imshow(r, cmap=pl.cm.gray)
    pl.colorbar()
    ax = pl.gca()
    for n, contour in enumerate(contours):
        ax.plot(contour[:, 1], contour[:, 0], linewidth=3)
    pl.axis('off')
    pl.show()
    
    
    
#############################################################
def processTiles(rasterPath, e, pinlist, divisions, tile_dims, subarray_dims, channel, exposure):
    """
    
    
    """
    chamber = 0
    time = 0
    arrayRepo = np.zeros(list(reversed(subarray_dims)), dtype = object)
    verticalLines_t, horizontalLines_t = divisions
    for index, value in np.ndenumerate(arrayRepo):
        indexList = list(index)
        d_corners = getCorners((index[1], index[0]), horizontalLines_t, verticalLines_t)
        chipAttrs = {'chamber': chamber,'array': index,'time': time}
        d = exp.Device('s1', 'd{}.{}.{}'.format(chamber, *indexList), tile_dims, pinlist, d_corners, attrs =  chipAttrs)
        e.addDevices([d])
        chip = collections.ChipImage(d, rasterPath, d.attrs, d.corners, pinlist, channel, exposure)
        chip.stamp()
        arrayRepo[index[0], index[1]] = chip
    return arrayRepo