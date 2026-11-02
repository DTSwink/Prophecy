"""Preserve verified incremental-model weights and full preparation accounting."""
import hashlib,json
import torch
from supermimic_kaggle import api,token_client,OUT


def prepare():
    ref='madmad74100/prophecy-supermimic-increment-audit'
    status=api().kernels_status(ref)
    assert type(status).to_dict(status)['status']=='COMPLETE'
    folder=OUT/'increment-model-dataset';folder.mkdir(exist_ok=True)
    receipt_path=OUT/'increment-model-dataset-upload.json'
    path=folder/'increments-audited-world.pt'
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==receipt['sha256']
        print('EXISTING_INCREMENT_MODEL',json.dumps(receipt));return
    paired=json.loads((OUT/'prophecy-supermimic-increment-audit-reports/verified-model-comparison.json').read_text())
    assert paired['shared_identical_dataset'] and not paired['actor_changed']
    report=json.loads((OUT/'prophecy-supermimic-increment-audit-reports/increments/result.json').read_text())
    assert report['complete'] and report['policy_parameter_delta_l2']==0
    assert report['normalization']['heldout_worlds_excluded']
    assert report['checks'][-1]['h1']['state_nse']<.05
    hashes=[]
    for _ in range(2):
        with token_client() as client:
            http=client._http_client
            url=http._endpoint.rstrip('/')+'/api/v1/kernels/output/download/'+ref+'/increments/world_model.pt'
            with http._session.get(url,params={'versionNumber':1},stream=True,timeout=(15,60)) as response:
                response.raise_for_status();digest=hashlib.sha256()
                with path.with_suffix('.partial').open('wb') as output:
                    for chunk in response.iter_content(1024*1024):output.write(chunk);digest.update(chunk)
                hashes.append(digest.hexdigest())
    assert hashes[0]==hashes[1]
    weights=torch.load(path.with_suffix('.partial'),map_location='cpu',weights_only=True)
    assert weights['increment_model']
    assert int(weights['model']['norm_count'])==report['normalization']['training_transitions']
    assert all(torch.isfinite(v).all() for v in weights['model'].values())
    path.with_suffix('.partial').replace(path)
    receipt=dict(source=ref,version=1,sha256=hashes[0],bytes=path.stat().st_size,
        fit_seconds=report['fit_seconds'],collection_seconds=report['collection_seconds'],
        worker_setup_seconds=report['provenance']['setup_and_baseline_seconds'],
        total_audit_seconds=report['total_audit_seconds'],parent_setup_seconds=52.859164746,
        normalization_seconds=report['normalization']['seconds'],
        accounting='Post-fit diagnostic; add prior fitting, collection, calibration and setup to end-to-end costs.')
    (folder/'increment-model-provenance.json').write_text(json.dumps(receipt,indent=2))
    metadata=dict(title='Prophecy SuperMimic Increment Model',id='madmad74100/prophecy-supermimic-increment-model',
        licenses=[{'name':'other'}],description='Private trained dynamics model; original policy unchanged.')
    (folder/'dataset-metadata.json').write_text(json.dumps(metadata))
    response=api().dataset_create_new(str(folder),public=False,quiet=True,convert_to_csv=False)
    receipt['response']=str(response)
    receipt_path.write_text(json.dumps(receipt,indent=2));print('INCREMENT_MODEL_UPLOADED',json.dumps(receipt))


if __name__=='__main__':prepare()
