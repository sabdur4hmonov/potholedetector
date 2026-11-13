"""Synthetic-only full-frame RDD conversion, negatives, deterministic split and checksum pin."""
import importlib.util
import json
from pathlib import Path
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'ml/prepare_rdd2022.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
checks = 0
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for i, damage in enumerate(('D40', 'D00', 'D10')):
        country = root / 'Japan/train'
        (country / 'annotations/xmls').mkdir(parents=True, exist_ok=True)
        (country / 'images').mkdir(exist_ok=True)
        Image.new('RGB',(60,30),(i*60,20,40)).save(country / f'images/frame{i}.jpg')
        xml = f'<annotation><size><width>60</width><height>30</height></size><object><name>{damage}</name><bndbox><xmin>11</xmin><ymin>6</ymin><xmax>30</xmax><ymax>20</ymax></bndbox></object></annotation>'
        path = country / f'annotations/xmls/frame{i}.xml'
        path.write_text(xml)
        w,h,boxes = m.voc_boxes(path)
        assert (w,h) == (60,30)
        assert boxes == ([[10.,5.,20.,15.]] if damage == 'D40' else [])
        checks += 2
    first = m.prepare(root / 'Japan',root / 'out1')
    second = m.prepare(root / 'Japan',root / 'out2')
    assert first == second
    assert first['countries']['Japan'] == dict(images=3, boxes=1, positives=1, negatives=2)
    checks += 2
    splits = [json.loads((root/f'out1/annotations/{s}.json').read_text()) for s in ('train','val','test')]
    assert sum(len(s['images']) for s in splits) == 3
    assert sum(len(s['annotations']) for s in splits) == 1
    names = [i['file_name'] for s in splits for i in s['images']]
    assert len(names) == len(set(names))
    for file in (root/'out1/images').iterdir():
        assert Image.open(file).size == (60,30)
    checks += 4
    pins=root/'pins.json'; pins.write_text('{"rdd2022_sha256":null}')
    archive=root/'source.zip'; archive.write_bytes(b'synthetic-not-a-dataset')
    digest=m.verify_archive(archive,pins)
    assert json.loads(pins.read_text())['rdd2022_sha256'] == digest
    archive.write_bytes(b'changed')
    try:
        m.verify_archive(archive,pins)
        raise AssertionError('Changed bytes accepted')
    except ValueError:
        pass
    checks += 2
    assert m.country_for(Path('RDD2022/China_Drone/train')) is None
    checks += 1
print(f'ML PREPARATION PASS ({checks} checks; three tiny VOC fixtures, no network/training)')
