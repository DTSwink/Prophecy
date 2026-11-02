"""Preserve the completed isolated run and hash only the two models we reuse."""
import hashlib
import json
import shutil
from supermimic_kaggle import OUT, api, token_client


def main():
    ref='madmad74100/prophecy-ppo-world-race'
    a=api(); status=a.kernels_status(ref)
    assert type(status).to_dict(status)['status']=='COMPLETE'
    source=OUT/'prophecy-ppo-world-race-reports'
    assert json.loads((source/'verified-comparison.json').read_text())['comparison_timing']['approximately_matched']
    archive=OUT/'prophecy-ppo-world-race-v1-reports'
    if not archive.exists():shutil.copytree(source,archive)
    shutil.copy2(OUT/'ppo-world-launch.json',OUT/'ppo-world-v1-launch.json')
    folder=OUT/'ppo-world-v1-models';folder.mkdir(exist_ok=True)
    receipt=dict(ref=ref,version=1,files={})
    for name in ['world_model.pt','policy_final.pt']:
        dest=folder/name
        if not dest.exists():
            with token_client() as client:
                http=client._http_client
                response=http._session.get(http._endpoint.rstrip('/')+'/api/v1/kernels/output/download/'+ref+'/ppo_world/'+name,timeout=(10,90))
                response.raise_for_status();dest.write_bytes(response.content)
        receipt['files'][name]=dict(bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    (folder/'provenance.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':main()
