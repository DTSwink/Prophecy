"""Overlap independent critic and actor work without changing sampling order."""
import math
import torch


class ConcurrentUpdate:
    def __init__(self, agent):
        self.agent = agent
        self.original = agent._update_model
        actor = {p.data_ptr() for p in agent._actor_optimizer._param_list}
        critic = {p.data_ptr() for p in agent._critic_optimizer._param_list}
        assert not actor.intersection(critic), 'Shared parameters cannot overlap'
        self.stream = torch.cuda.Stream()

    def __call__(self):
        a = self.agent
        a.train()
        worlds = a.get_num_envs()
        samples = a._exp_buffer.get_sample_count()
        cb = int(math.ceil(a._critic_batch_size * worlds))
        cs = int(math.ceil(float(samples) / cb)) * a._critic_epochs
        ab = int(math.ceil(a._actor_batch_size * worlds))
        astep = int(math.ceil(float(samples) / ab)) * a._actor_epochs
        sample = a._exp_buffer.sample
        # Sample in the original order, before the actor draws its KL subset.
        # Each batch owns its gathered storage, including across buffer reshuffles.
        batches = [sample(cb) for _ in range(cs)]
        current = torch.cuda.current_stream()
        self.stream.wait_stream(current)
        for batch in batches:
            for value in batch.values():
                if isinstance(value, torch.Tensor):
                    value.record_stream(self.stream)
        pending = iter(batches)
        try:
            def prepared(size):
                assert size == cb
                return next(pending)
            a._exp_buffer.sample = prepared
            with torch.cuda.stream(self.stream):
                critic_info = a._update_critic(cb, cs)
        finally:
            a._exp_buffer.sample = sample
        try:
            actor_info = a._update_actor(ab, astep)
        finally:
            current.wait_stream(self.stream)
        for value in critic_info.values():
            if isinstance(value, torch.Tensor):
                value.record_stream(current)
        return {**critic_info, **actor_info}
