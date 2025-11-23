import numpy as np

def hillshade(array, azimuth=315, altitude=45):
    x, y = np.gradient(array)
    slope = np.pi/2 - np.arctan(np.sqrt(x*x + y*y))
    aspect = np.arctan2(-x, y)
    az = np.radians(azimuth)
    alt = np.radians(altitude)
    shaded = np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    return np.clip(shaded, 0, 1)

