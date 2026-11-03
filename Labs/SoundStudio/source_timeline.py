"""Map rendered playback onto a stable source timeline, including circular trim."""
from dataclasses import dataclass
import numpy as np
from creative_audio import trim_duration


@dataclass(frozen=True)
class SourceTimeline:
    duration: float
    settings: object
    rate: int = 48000

    @property
    def start(self):return min(self.duration,max(0,self.settings.start))

    @property
    def end(self):return self.duration if self.settings.end is None else min(self.duration,max(0,self.settings.end))

    @property
    def length(self):return trim_duration(self.settings,self.duration)

    @property
    def factor(self):return (self.settings.grain_length if self.settings.granular else 1.)/self.settings.speed

    def excluded(self):
        if self.length>=self.duration-1e-9:return []
        if self.end>self.start:return [(0.,self.start),(self.end,self.duration)]
        return [(self.end,self.start)]

    def source_position(self,seconds):
        distance=max(0,seconds/self.factor)
        # A reverb tail remains at the endpoint; it must not loop the marker.
        if distance>=self.length:
            return self.start % self.duration if self.settings.reverse else self.end
        if self.settings.reverse:distance=max(0,self.length-distance-1/self.rate)
        return (self.start+distance) % self.duration

    def output_positions(self,positions):
        positions=np.asarray(positions)
        distance=np.mod(positions-self.start,self.duration)
        if self.settings.reverse:distance=np.maximum(0,self.length-distance-1/self.rate)
        return distance*self.factor

    def output_position(self,position):
        distance=(position-self.start) % self.duration
        if position==self.duration and self.start==0:distance=self.duration
        if distance>self.length:
            # Seek in an excluded section to its nearest circular boundary.
            distance=self.length if distance-self.length<=self.duration-distance else 0.
        if self.settings.reverse:distance=max(0,self.length-distance-1/self.rate)
        return distance*self.factor

    def contains(self,positions):
        if self.length>=self.duration-1e-9:return np.ones(np.shape(positions),dtype=bool)
        return np.mod(np.asarray(positions)-self.start,self.duration)<self.length


def mapped_waveform(source,source_rate,processed,processed_rate,timeline,start,span,bins=700):
    """Min/max actual samples in each source-time column; excluded audio stays visible.

    Keep reverse and wrap boundaries between bins, never reduce across the seam.
    Granular output maps selection progress, not provenance of individual grains.
    """
    bins=max(1,min(bins,round(span*source_rate)))
    edges=np.linspace(start,start+span,bins+1)
    centers=(edges[:-1]+edges[1:])/2
    def envelope(samples,rate,left,right):
        a=np.clip(np.floor(np.minimum(left,right)*rate+1e-7).astype(int),0,len(samples)-1)
        b=np.clip(np.ceil(np.maximum(left,right)*rate-1e-7).astype(int),a+1,len(samples))
        # reduceat uses exclusive boundaries. A final duplicate last sample is
        # harmless and allows an exact end boundary without copying the buffer.
        indices=np.stack((a,np.minimum(b,len(samples)-1)),axis=1).ravel()
        lo=np.minimum.reduceat(samples,indices,axis=0)[::2]
        hi=np.maximum.reduceat(samples,indices,axis=0)[::2]
        last=b==len(samples)
        lo[last]=np.minimum(lo[last],samples[-1]);hi[last]=np.maximum(hi[last],samples[-1])
        return np.stack((lo,hi),axis=1)
    peaks=envelope(source,source_rate,edges[:-1],edges[1:])
    if processed is not None:
        if peaks.shape[2]!=processed.shape[1]:
            if processed.shape[1]==1:peaks=envelope(source.mean(axis=1,keepdims=True),source_rate,edges[:-1],edges[1:])
            else:peaks=np.repeat(peaks,processed.shape[1],axis=2)
        selected=timeline.contains(centers)
        midpoint=timeline.output_positions(centers)
        # Reversing discrete samples exchanges inclusive/exclusive bin edges.
        if timeline.settings.reverse:midpoint+=timeline.factor/source_rate
        half=span/bins*timeline.factor/2
        left=np.maximum(0,midpoint-half)
        right=np.minimum(timeline.length*timeline.factor,midpoint+half)
        wet=envelope(processed,processed_rate,left,right)
        peaks[selected]=wet[selected]
    return peaks,centers
