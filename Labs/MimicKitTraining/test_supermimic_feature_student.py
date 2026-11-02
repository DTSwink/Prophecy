import unittest
import torch
from torch import nn
from supermimic_feature_student import FeatureStudent,fit_head


class Checks(unittest.TestCase):
    def test_reuses_frozen_features_and_fits_unseen_linear_correction(self):
        torch.manual_seed(91);torch.set_num_threads(2)
        feature=nn.Linear(5,5,bias=False)
        with torch.no_grad():feature.weight.copy_(torch.eye(5))
        original={k:v.clone() for k,v in feature.state_dict().items()}
        student=FeatureStudent(feature,5,3)
        self.assertTrue(all(not p.requires_grad for p in student.features.parameters()))
        self.assertTrue(torch.equal(student(torch.randn(10,5)),torch.zeros(10,3)))
        data={}
        for key,n in [('teacher_train',240),('teacher_valid',80),('anchor_train',240),('anchor_valid',80)]:
            x=torch.randn(n,5)*.3
            if key.startswith('anchor'):x[:,:3]=0
            data[key]=(x,.08*x[:,:3])
        result=fit_head(student,data,chunk=31)
        self.assertGreater(result['selected_audit']['teacher_valid']['explained_target_energy'],.99)
        self.assertLess(result['selected_audit']['anchor_valid']['mse'],1e-6)
        self.assertTrue(all(torch.equal(v,feature.state_dict()[k]) for k,v in original.items()))
        self.assertTrue(all(torch.equal(v,student.features.state_dict()[k]) for k,v in original.items()))
        self.assertTrue(torch.all(student(torch.randn(20,5)*100).abs()<=.225))

    def test_validation_targets_never_enter_ridge_solve(self):
        torch.manual_seed(17)
        data={k:(torch.randn(50,3),torch.randn(50,2)*.01) for k in ['teacher_train','teacher_valid','anchor_train','anchor_valid']}
        a=FeatureStudent(nn.Identity(),3,2);b=FeatureStudent(nn.Identity(),3,2)
        fit_head(a,data,alphas=(.1,))
        changed={k:(x,100*y if 'valid' in k else y) for k,(x,y) in data.items()}
        fit_head(b,changed,alphas=(.1,))
        self.assertTrue(all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items()))


if __name__=='__main__':unittest.main()
