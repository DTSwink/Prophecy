"""Meaningful data preservation and live OpenGL/UI workflow checks, isolated from user datasets."""
from pathlib import Path
import hashlib
import json
import tempfile
import time
import unittest
from types import SimpleNamespace
import numpy as np
from motion import read_motion, clip_record, write_cut, save_dataset, load_dataset, dataset_name

ORIGINAL=Path.home()/'Downloads/LaFAN1/walk1_subject1.bvh'
RESOLVED=Path.home()/'Downloads/LAFAN-Re-solved/bvh/walk1_subject1.bvh'


class DataChecks(unittest.TestCase):
    def test_fk_and_channel_order(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'test.bvh'
            p.write_text('''HIERARCHY
ROOT Hips
{
 OFFSET 50 200 30
 CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation
 JOINT Arm
 {
  OFFSET 100 0 0
  CHANNELS 3 Xrotation Yrotation Zrotation
  End Site
  {
   OFFSET 100 0 0
  }
 }
}
MOTION
Frames: 2
Frame Time: 0.033333333333
10 100 0 90 0 0 0 0 0
10 100 0 0 90 0 0 0 0
''')
            m=read_motion(p)
            np.testing.assert_allclose(m.positions[0],[[.1,1,0],[.1,2,0],[.1,3,0]],atol=1e-6)
            np.testing.assert_allclose(m.positions[1],[[.1,1,0],[.1,1,-1],[.1,1,-2]],atol=1e-6)
            text=p.read_text().replace('CHANNELS 3 Xrotation Yrotation Zrotation',
                'CHANNELS 6 Xposition Yposition Zposition Xrotation Yrotation Zrotation')
            text=text.replace('10 100 0 90 0 0 0 0 0','10 100 0 90 0 0 100 0 0 0 0 0')
            text=text.replace('10 100 0 0 90 0 0 0 0','10 100 0 0 90 0 100 0 0 0 0 0')
            p.write_text(text)
            np.testing.assert_allclose(read_motion(p).positions,m.positions,atol=1e-6)

    def test_real_cuts_and_revisions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            clips=[]; hashes={}
            for path in (ORIGINAL,RESOLVED):
                m=read_motion(path);hashes[path]=m.sha256
                np.testing.assert_allclose(m.positions[0,0],m.values[0,:3]*.01,atol=1e-6)
                self.assertLess(m.positions[0,:,1].min(),.20)
                self.assertLess(np.ptp(m.positions[0],axis=0).max(),2.5)
                for a,b in ((0,0),(10,29),(m.count-3,m.count-1)):
                    out=root/f'{path.parent.name}_{a}.bvh';write_cut(m,out,a,b)
                    cut=read_motion(out)
                    self.assertEqual(cut.rows,m.rows[a:b+1])
                    self.assertEqual(cut.dt,m.dt)
                    self.assertEqual(cut.names,m.names)
                    np.testing.assert_array_equal(cut.values,m.values[a:b+1])
                    np.testing.assert_allclose(cut.positions,m.positions[a:b+1],atol=2e-6)
                clips.append(clip_record(m,10,29))
            p=save_dataset(root/'datasets','First dataset',clips)
            first=json.loads(p.read_text())
            archived=p.parent / Path(first['clips'][0]['file']).parent / 'manifest.json'
            self.assertEqual(len(load_dataset(archived)[1]),2)
            name,restored=load_dataset(p)
            self.assertEqual(name,'First dataset');self.assertEqual(len(restored),2)
            self.assertEqual([x['frames'] for x in restored],[20,20])
            q=save_dataset(root/'datasets','Second dataset',restored)
            self.assertTrue(q.exists())
            save_dataset(root/'datasets','First dataset',clips[:1])
            self.assertEqual(len(json.loads(p.read_text())['clips']),1)
            for row in first['clips']:self.assertTrue((p.parent/row['file']).exists())
            prior=p.read_bytes();invalid=[{**clips[0],'source_sha256':'wrong'}]
            with self.assertRaises(ValueError):save_dataset(root/'datasets','First dataset',invalid)
            self.assertEqual(p.read_bytes(),prior)
            for path,digest in hashes.items():self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)

    def test_invalid_names(self):
        for name in ('../bad','NUL','a/b','a\\b','thing:bad','CON.txt',''):
            with self.assertRaises(ValueError):dataset_name(name)


def gui_check():
    from app import Cutter
    from OpenGL import GL
    with tempfile.TemporaryDirectory() as temp:
        app=Cutter(Path(temp),smoke=True)
        def wait(predicate,seconds=40):
            until=time.monotonic()+seconds
            while not predicate():
                app.update();time.sleep(.02)
                if app.last_error:raise AssertionError(app.last_error)
                if time.monotonic()>until:raise TimeoutError('UI did not finish')
        try:
            wait(lambda:app.motion is not None)
            app.load(ORIGINAL,True);wait(lambda:app.motion.path==ORIGINAL and str(app.add_button['state'])=='normal')
            app.start=10;app.end=50;app.update_controls()
            x=app.timeline_x(app.end)
            app.timeline_down(SimpleNamespace(x=x,y=29))
            app.timeline_move(SimpleNamespace(x=app.timeline_x(70),y=29))
            app.timeline_up(SimpleNamespace(x=app.timeline_x(70),y=29))
            assert app.end==70
            app.start_var.set('20');app.end_var.set('49');app.apply_range();app.add_button.invoke()
            self_clip=app.clips[0];assert self_clip['frames']==30
            app.start_var.set('80');app.end_var.set('99');app.apply_range();app.add_button.invoke()
            assert len(app.clips)==2
            app.cut_tree.selection_set('1');app.move_cut(-1)
            assert app.clips[0]['start']==80
            app.name_var.set('UI test');app.save_button.invoke();wait(lambda:not app.busy_save)
            assert (Path(temp)/'datasets/UI test/dataset.json').exists()
            app.name_var.set('UI second dataset');app.save_button.invoke();wait(lambda:not app.busy_save)
            assert (Path(temp)/'datasets/UI second dataset/dataset.json').exists()
            app.select_cut();wait(lambda:not app.from_source)
            assert (app.start,app.end)==(80,99)
            app.toggle();previous=app.frame
            wait(lambda:app.frame!=previous)
            app.toggle();app.draw()
            app.viewport.tkMakeCurrent()
            w,h=app.viewport.winfo_width(),app.viewport.winfo_height()
            # WGL window pixels are undefined when another window occludes the
            # test. Render the exact production draw routine into an FBO instead.
            fbo=GL.glGenFramebuffers(1);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,fbo)
            color=GL.glGenTextures(1);GL.glBindTexture(GL.GL_TEXTURE_2D,color)
            GL.glTexImage2D(GL.GL_TEXTURE_2D,0,GL.GL_RGB,w,h,0,GL.GL_RGB,GL.GL_UNSIGNED_BYTE,None)
            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0,GL.GL_TEXTURE_2D,color,0)
            depth=GL.glGenRenderbuffers(1);GL.glBindRenderbuffer(GL.GL_RENDERBUFFER,depth)
            GL.glRenderbufferStorage(GL.GL_RENDERBUFFER,GL.GL_DEPTH_COMPONENT24,w,h)
            GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER,GL.GL_DEPTH_ATTACHMENT,GL.GL_RENDERBUFFER,depth)
            assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)==GL.GL_FRAMEBUFFER_COMPLETE
            app.render();GL.glFinish();GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
            pixels=np.frombuffer(GL.glReadPixels(0,0,w,h,GL.GL_RGB,GL.GL_UNSIGNED_BYTE),np.uint8).reshape(h,w,3)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,0)
            GL.glDeleteTextures([color]);GL.glDeleteRenderbuffers(1,[depth]);GL.glDeleteFramebuffers(1,[fbo])
            assert np.count_nonzero((pixels[:,:,0]>200)&(pixels[:,:,1]>90))>50,'Skeleton not rendered'
            assert not app.last_error
            app.write_draft()
            assert len(json.loads((Path(temp)/'session.json').read_text())['clips'])==2
            identity=json.loads((Path(temp)/'app-identity.json').read_text())
            assert identity['app_id']=='Prophecy.LafanCutter.Desktop.1'
            assert identity['small_icon'] and identity['large_icon']
            from PIL import Image
            evidence=Path(__file__).resolve().parents[2]/'Saved/Diagnostics/LafanCutter20261016'
            evidence.mkdir(parents=True,exist_ok=True)
            Image.fromarray(pixels[::-1]).save(evidence/'preview.png')
            report=dict(ui='pass',render='pass',trim='pass',slider='pass',save_two_names='pass',playback='pass',draft='pass',identity=identity)
            (evidence/'verification.json').write_text(json.dumps(report,indent=2))
            return report
        finally:
            app.playing=False;app.close()


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DataChecks))
    if not result.wasSuccessful():raise SystemExit(1)
    print(json.dumps(gui_check()))
