from path import xyzPath
import numpy as np

def re3(path, time):
    """RE3 Running Equation"""
                        
    segCount = path.get_point_count() - 1
    if segCount <= 0:
        return 0

    segTime = time * 3600 / segCount   # seconds per segment
    if segTime == 0:
        segTime = 1e-9  # avoid division-by-zero but keep tiny
    
    segments = path.get_segments()
    dist = segments[:, 3]     # segment lengths
    rise = segments[:, 2]     # elevation change
    
  
    term1 = 4.43 * time
    
    term2 = 1.39 * np.sum(dist)
    
    
    term3 = 0.185 * np.sum((dist ** 2) / segTime)
    
    
    exponent1 = (rise/dist + 0.43)
    exponent2 = (1 - 1.056 ** exponent1)
 
    term4 = 30.43 * np.sum(rise * (1 - 1.133 ** exponent2))
    
    totalCost = term1 + term2 + term3 + term4
    
    print(totalCost)
    return totalCost




def acsm_equation(path, time):
    """ACSM Walking Equation"""
    segCount = path.get_point_count() - 1
    segTime = time * 3600 / (segCount) #Time is provided in hours, convert to seconds
    segments = path.get_segments()

    totalCost = 0.1 * sum(segments[:,3]) + 1.8 * sum(segments[:,2]) + time * 0.0583
    
    return totalCost

def ihc(path, time):
    "I Hate To Climb Equation"
    segs = path.get_segments()
    dist = sum(segs[:,3])
    segDeltaZ = segs[:, 2] 
    segClimb = segDeltaZ[segDeltaZ > 0]
    print(segDeltaZ)
    return sum(segClimb) + dist/300