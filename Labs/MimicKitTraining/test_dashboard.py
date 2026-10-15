import tempfile
import json
import unittest
from pathlib import Path
from tensorboard.compat.proto.event_pb2 import Event
from tensorboard.compat.proto.summary_pb2 import Summary
from tensorboard.summary.writer.event_file_writer import EventFileWriter
from dashboard import Dashboard,scalars


class DashboardTests(unittest.TestCase):
    def test_four_pose_terms_and_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';writer=EventFileWriter(str(source))
            terms={'body_pose_mse':.2,'head_height_band':.03,'pelvis_height_band':.02,'feet_lateral':.05,'total':.3}
            writer.add_event(Event(wall_time=1700000000,step=123,
                summary=Summary(value=[Summary.Value(tag='loss/'+k,simple_value=v) for k,v in terms.items()])))
            writer.close()
            d=Dashboard(dict(output=str(root/'out'),runs=[dict(name='pose_feet',objective='world_pose_mse',sources=[str(source)])]))
            self.assertEqual(d.update(),5);self.assertEqual(d.update(),0);d.close()
            data=scalars(root/'out/pose_feet')
            self.assertEqual(set(data),{'loss/'+k for k in terms})
            for k,v in terms.items():self.assertAlmostEqual(data['loss/'+k][0].value,v)

    def test_three_terms_and_total_without_fake_test_or_mse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';writer=EventFileWriter(str(source))
            terms={'early_pose':-.4,'tail_mse':.1,'joint_velocity':.2,'total':-.1}
            writer.add_event(Event(wall_time=1700000000,step=120,
                summary=Summary(value=[Summary.Value(tag='loss/'+k,simple_value=v) for k,v in terms.items()]+[
                    Summary.Value(tag='0_Main/Train_Return',simple_value=.1),
                    Summary.Value(tag='0_Main/Test_Return',simple_value=0)])))
            writer.close()
            (source/'status.json').write_text(json.dumps(dict(samples=120,updated_unix=1700000000,
                metrics=dict(mean_return=.1,num_eps=512))))
            d=Dashboard(dict(output=str(root/'out'),runs=[dict(name='tail',objective='timed_best_pose_tail',sources=[str(source)])]))
            self.assertEqual(d.update(),4);self.assertEqual(d.update(),0);d.close()
            data=scalars(root/'out/tail')
            self.assertEqual(set(data),{'loss/'+k for k in terms})
            for k,v in terms.items():self.assertAlmostEqual(data['loss/'+k][0].value,v)

    def test_resume_stitching_sign_samples_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources=[]
            for name,step,value in [('first',100,-.3),('resumed',200,-.2)]:
                path=root/name;sources.append(str(path));writer=EventFileWriter(str(path))
                writer.add_event(Event(wall_time=1700000000+step,step=step,
                    summary=Summary(value=[Summary.Value(tag='0_Main/Test_Return',simple_value=value),
                        Summary.Value(tag='0_Main/Train_Return',simple_value=0),
                        Summary.Value(tag='1_Info/Train_Episodes',simple_value=0)])))
                writer.close()
            manifest={'output':str(root/'out'),'runs':[{'name':'dated_4096','objective':'neutral_pose_mse','sources':sources}]}
            d=Dashboard(manifest);self.assertEqual(d.update(),2);self.assertEqual(d.update(),0);d.close()
            values=scalars(root/'out/dated_4096')['loss/test'];self.assertEqual([e.step for e in values],[100,200])
            self.assertAlmostEqual(values[0].value,.3);self.assertAlmostEqual(values[1].value,.2)
            self.assertEqual(values[0].wall_time,1700000100)
            d=Dashboard(manifest);self.assertEqual(d.update(),0);d.close()


    def test_short_failed_run_recovers_exact_status_loss_without_fake_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir()
            (source/'status.json').write_text(json.dumps(dict(samples=167936,updated_unix=1000,
                metrics=dict(mean_return=-.248998716,num_eps=3584))))
            manifest=dict(output=str(root/'out'),runs=[dict(name='failed128',objective='neutral_pose_mse',sources=[str(source)])])
            d=Dashboard(manifest);self.assertEqual(d.update(),1);self.assertEqual(d.update(),0);d.close()
            data=scalars(root/'out/failed128');self.assertEqual(list(data),['loss/train'])
            self.assertAlmostEqual(data['loss/train'][0].value,.248998716)
            self.assertEqual(data['loss/train'][0].step,167936)


if __name__=='__main__':unittest.main()
