"""Experimental fixed-batch forward/backward graphs. Adam and KL stay eager."""
import torch
from util import mp_util

class GraphedLoss:
    def __init__(self,fn,optimizer,batch,key):
        assert not mp_util.enable_mp()
        self.fn=fn;self.optimizer=optimizer;self.key=key
        self.batch={k:v.detach().clone() for k,v in batch.items()}
        params=optimizer._param_list
        previous=[p.grad for p in params]
        for p in params:p.grad=torch.zeros_like(p)
        stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
        def calculate():
            for p in params:p.grad.zero_()
            info=fn(self.batch);info[key].backward();return info
        with torch.cuda.stream(stream):
            for _ in range(3):calculate()
        torch.cuda.current_stream().wait_stream(stream)
        self.graph=torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph,stream=stream):self.info=calculate()
        self.grads=[p.grad for p in params]
        for p,g in zip(params,previous):p.grad=g
        self.original_step=optimizer.step
        self.installed=False
    def __call__(self,batch):
        if not torch.is_grad_enabled():return self.fn(batch)
        assert batch.keys()==self.batch.keys()
        for k,v in batch.items():
            assert v.shape==self.batch[k].shape and v.dtype==self.batch[k].dtype
            self.batch[k].copy_(v)
        for p,g in zip(self.optimizer._param_list,self.grads):p.grad=g
        self.graph.replay()
        return self.info
    def step(self,loss):
        if loss is not self.info[self.key]:return self.original_step(loss)
        o=self.optimizer
        if o._enable_grad_clip():o._clip_grads(o._grad_clip)
        o._optimizer.step();o._steps+=1
    def install(self):self.optimizer.step=self.step;self.installed=True
    def uninstall(self):self.optimizer.step=self.original_step;self.installed=False
