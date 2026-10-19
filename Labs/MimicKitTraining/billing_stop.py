"""Stop one owned pod; a sent HTTP request is not confirmation of stopped billing."""
import json
import time
from pathlib import Path

import requests


def stop_and_confirm(pod_id, api_key, receipt_path, reason, request=requests.request, sleep=time.sleep):
    url='https://rest.runpod.io/v1/pods/'+pod_id
    headers={'Authorization':'Bearer '+api_key}
    receipt_path=Path(receipt_path)
    attempt=0
    while True:
        attempt+=1
        receipt=dict(pod=pod_id,reason=reason,attempt=attempt,time=time.time(),confirmed=False)
        try:
            response=request('POST',url+'/stop',headers=headers,timeout=15)
            response.raise_for_status()
            response=request('GET',url,headers=headers,timeout=15)
            response.raise_for_status()
            state=response.json()
            if state.get('id')!=pod_id:
                raise ValueError('Unexpected pod identity in stop verification')
            receipt['state']=state.get('desiredStatus')
            receipt['confirmed']=receipt['state']=='EXITED'
        except Exception as error:
            receipt['error']=type(error).__name__
            receipt['http_status']=getattr(getattr(error,'response',None),'status_code',None)
        temporary=receipt_path.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(receipt));temporary.replace(receipt_path)
        except OSError as error:
            print('Cannot save billing receipt: '+type(error).__name__,flush=True)
        if receipt['confirmed']:return receipt
        print('BILLING STOP NOT CONFIRMED: '+json.dumps(receipt),flush=True)
        sleep(5)
