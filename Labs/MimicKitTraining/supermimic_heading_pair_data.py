"""Preserve the matched heading-audit models, with fit costs and hashes."""
import hashlib,json
import torch
from supermimic_kaggle import api,token_client,OUT


def prepare():
    ref='madmad74100/prophecy-supermimic-heading-audit'
    status=api().kernels_status(ref)
    assert type(status).to_dict(status)['status']=='COMPLETE'
    folder=OUT/'heading-pair-dataset';folder.mkdir(exist_ok=True)
    receipt_path=OUT/'heading-pair-dataset-upload.json'
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        for name,metadata in receipt['models'].items():
            assert hashlib.sha256((folder/(name+'-paired-world.pt')).read_bytes()).hexdigest()==metadata['sha256']
        print('EXISTING_HEADING_PAIR',json.dumps(receipt));return
    paired=json.loads((OUT/'prophecy-supermimic-heading-audit-reports/verified-model-comparison.json').read_text())
    assert paired['shared_identical_dataset'] and not paired['actor_changed']
    receipt=dict(source=ref,version=1,models={})
    for name,remote_name in [('residual','residual'),('heading','equivariant')]:
        report=json.loads((OUT/'prophecy-supermimic-heading-audit-reports'/remote_name/'result.json').read_text())
        assert report['complete'] and report['policy_parameter_delta_l2']==0 and report['gradient_audit']['passed']
        path=folder/(name+'-paired-world.pt');hashes=[]
        for _ in range(2):
            with token_client() as client:
                http=client._http_client
                url=http._endpoint.rstrip('/')+'/api/v1/kernels/output/download/'+ref+'/'+remote_name+'/world_model.pt'
                with http._session.get(url,params={'versionNumber':1},stream=True,timeout=(15,60)) as response:
                    response.raise_for_status();digest=hashlib.sha256()
                    with path.with_suffix('.partial').open('wb') as output:
                        for chunk in response.iter_content(1024*1024):output.write(chunk);digest.update(chunk)
                    hashes.append(digest.hexdigest())
        assert hashes[0]==hashes[1]
        weights=torch.load(path.with_suffix('.partial'),map_location='cpu',weights_only=True)
        assert weights['heading_equivariant']==(name=='heading')
        assert all(torch.isfinite(v).all() for v in weights['model'].values())
        path.with_suffix('.partial').replace(path)
        receipt['models'][name]=dict(sha256=hashes[0],bytes=path.stat().st_size,
            fit_seconds=report['fit_seconds'],collection_seconds=report['collection_seconds'],
            worker_setup_seconds=report['provenance']['setup_and_baseline_seconds'],
            total_audit_seconds=report['total_audit_seconds'],parent_setup_seconds=48.254545587,
            accounting='Post-fit diagnostic; add prior fitting, collection and setup to end-to-end costs.')
    (folder/'heading-pair-provenance.json').write_text(json.dumps(receipt,indent=2))
    metadata=dict(title='Prophecy SuperMimic Heading Pair',id='madmad74100/prophecy-supermimic-heading-pair',
        licenses=[{'name':'other'}],description='Private matched model audit weights, original policy unchanged.')
    (folder/'dataset-metadata.json').write_text(json.dumps(metadata))
    response=api().dataset_create_new(str(folder),public=False,quiet=True,convert_to_csv=False)
    receipt['response']=str(response)
    receipt_path.write_text(json.dumps(receipt,indent=2));print('HEADING_PAIR_UPLOADED',json.dumps(receipt))


if __name__=='__main__':prepare()
