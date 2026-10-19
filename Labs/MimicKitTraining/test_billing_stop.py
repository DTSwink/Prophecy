"""Billing stop must survive rejected requests and verify the exact owned pod."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import requests
from billing_stop import stop_and_confirm


class BillingTests(unittest.TestCase):
    def test_retries_until_verified(self):
        states=iter(['RUNNING','EXITED'])
        calls=[]
        def request(method,url,**kwargs):
            calls.append((method,url))
            if len(calls)==1:
                raise requests.HTTPError(response=SimpleNamespace(status_code=403))
            value={'id':'owned','desiredStatus':next(states)} if method=='GET' else {}
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:value)
        with tempfile.TemporaryDirectory() as folder:
            receipt=Path(folder)/'stop.json'
            result=stop_and_confirm('owned','dummy',receipt,'test',request=request,sleep=lambda _:None)
            self.assertTrue(result['confirmed'])
            self.assertEqual(result['attempt'],3)
            self.assertEqual(json.loads(receipt.read_text())['state'],'EXITED')
        self.assertEqual([m for m,_ in calls],['POST','POST','GET','POST','GET'])
        self.assertTrue(all('/pods/owned' in url for _,url in calls))

    def test_wrong_identity_is_not_confirmation(self):
        ids=iter(['unrelated','owned'])
        def request(method,url,**kwargs):
            value={'id':next(ids),'desiredStatus':'EXITED'} if method=='GET' else {}
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:value)
        with tempfile.TemporaryDirectory() as folder:
            result=stop_and_confirm('owned','dummy',Path(folder)/'stop.json','test',request=request,sleep=lambda _:None)
            self.assertEqual(result['attempt'],2)


if __name__=='__main__':unittest.main()
