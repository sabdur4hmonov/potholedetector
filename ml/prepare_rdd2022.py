"""Prepare full-frame D40-only COCO. Large downloads run on Colab only."""
import argparse
import hashlib
import json
import random
import shutil
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
COUNTRIES = ('Japan', 'India', 'Czech', 'Norway', 'United_States', 'China_MotorBike')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def verify_archive(path, pins_path):
    digest = sha256(path)
    print('RDD2022 SHA-256:', digest, flush=True)
    pins = json.loads(Path(pins_path).read_text())
    if pins.get('rdd2022_sha256') and pins['rdd2022_sha256'] != digest:
        raise ValueError('RDD2022 SHA-256 mismatch')
    if not pins.get('rdd2022_sha256'):
        pins['rdd2022_sha256'] = digest
        Path(pins_path).write_text(json.dumps(pins, indent=2) + '\n')
        print('First-download pin recorded; retain pins.json with the training receipt.')
    return digest


def voc_boxes(xml):
    root = ET.parse(xml).getroot()
    w, h = int(root.findtext('size/width')), int(root.findtext('size/height'))
    if w <= 0 or h <= 0:
        raise ValueError('Invalid dimensions')
    boxes = []
    for obj in root.findall('object'):
        if obj.findtext('name', '').strip().upper() != 'D40':
            continue  # All cracks/other classes are hard negatives.
        b = obj.find('bndbox')
        x, y = max(0., float(b.findtext('xmin')) - 1), max(0., float(b.findtext('ymin')) - 1)
        right, bottom = min(w, float(b.findtext('xmax'))), min(h, float(b.findtext('ymax')))
        if not (0 <= x < right <= w and 0 <= y < bottom <= h):
            raise ValueError('Invalid D40 box')
        boxes.append([x, y, right - x, bottom - y])
    return w, h, boxes


def country_for(path):
    return next((c for c in COUNTRIES if c in path.parts), None)


def extract(archive, output):
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            p = PurePosixPath(item.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in item.filename:
                raise ValueError('Unsafe archive path')
            if 'China_Drone' in p.parts or not country_for(p) or item.is_dir():
                continue
            if p.suffix.lower() not in ('.xml', '.jpg', '.jpeg', '.png'):
                continue
            if item.file_size > 67108864 or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Oversize image or symlink')
            target = output.joinpath(*p.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as source, target.open('wb') as dest:
                shutil.copyfileobj(source, dest)


def owner_records(archive, output):
    from PIL import Image, ImageOps
    records, pending = [], []
    with zipfile.ZipFile(archive) as z:
        for row in json.loads(z.read('labels.json'))['images']:
            p = PurePosixPath(row['path'])
            if p.is_absolute() or '..' in p.parts or '\\' in str(p):
                raise ValueError('Unsafe owner frame path')
            label = row.get('label_yes_no', row.get('label'))
            yes = label in ('pothole', 'pothole_cavity', 'reportable', 'yes', 'Yes')
            no = label in ('not_pothole', 'not_reportable', 'no', 'No')
            if not (yes or no):
                continue
            if yes and not row.get('boxes'):
                pending.append({'path': str(p), 'reason': 'Image-level Yes needs human pothole boxes'})
                continue  # Never invent a box or treat a positive as a negative.
            item = z.getinfo(str(p))
            if item.file_size > 33554432:
                raise ValueError('Owner frame exceeds encoded budget')
            with z.open(item) as f, Image.open(f) as im:
                if im.width * im.height > 64000000:
                    raise ValueError('Owner frame exceeds pixel budget')
                im = ImageOps.exif_transpose(im).convert('RGB')
                target = output / (hashlib.sha256(str(p).encode()).hexdigest() + '.jpg')
                im.save(target, quality=95)  # Complete oriented frame, no EXIF/GPS.
                w, h = im.size
            boxes = row.get('boxes', []) if yes else []
            for x, y, bw, bh in boxes:
                if not (0 <= x < x + bw <= w and 0 <= y < y + bh <= h):
                    raise ValueError('Owner boxes must be full-frame COCO coordinates')
            records.append(('Owner', target, w, h, boxes))
    (output.parent / 'owner_positive_review.json').write_text(json.dumps(pending, indent=2))
    return records


def prepare(root, output, seed=20221105, dataset_hash=None, extra=None):
    output = Path(output)
    images = output / 'images'
    images.mkdir(parents=True, exist_ok=True)
    rows, seen = [], set()
    for xml in sorted(Path(root).rglob('*.xml')):
        country = country_for(xml)
        if not country or 'China_Drone' in xml.parts:
            continue
        candidates = [xml.parent.parent.parent / 'images' / (xml.stem + '.jpg'),
                      xml.parent.parent / 'images' / (xml.stem + '.jpg'),
                      xml.parent.parent / 'JPEGImages' / (xml.stem + '.jpg'), xml.with_suffix('.jpg')]
        source = next((p for p in candidates if p.is_file()), None)
        if source is None:
            raise ValueError(f'Annotated frame missing: {xml}')
        digest = sha256(source)
        if digest in seen:
            continue
        seen.add(digest)
        w, h, boxes = voc_boxes(xml)
        rows.append((country, source, w, h, boxes))
    if extra:
        rows.extend(owner_records(extra, images))
    if not rows:
        raise ValueError('No annotated frames; official unlabelled test frames are NOT negatives')
    splits = {s: [] for s in ('train', 'val', 'test')}
    rng = random.Random(seed)
    for country in (*COUNTRIES, 'Owner'):
        for positive in (False, True):
            selected = sorted((r for r in rows if r[0] == country and bool(r[4]) == positive), key=lambda r: str(r[1]))
            rng.shuffle(selected)
            a, b = int(len(selected) * .8), int(len(selected) * .9)
            for split, items in (('train', selected[:a]), ('val', selected[a:b]), ('test', selected[b:])):
                splits[split].extend(items)
    stats = {'dataset_sha256': dataset_hash, 'seed': seed, 'countries': {}, 'splits': {},
             'excluded': ['China_Drone', 'official unannotated test images'], 'full_frame': True}
    ann = output / 'annotations'
    ann.mkdir(exist_ok=True)
    for split, records in splits.items():
        coco = {'info': {'description': 'RDD2022 D40 full frames'}, 'images': [], 'annotations': [],
                'categories': [{'id': 1, 'name': 'pothole'}]}
        for i, (country, source, w, h, boxes) in enumerate(records, 1):
            name = sha256(source) + source.suffix.lower()
            target = images / name
            if source.resolve() != target.resolve() and not target.exists():
                shutil.copyfile(source, target)  # Entire original image.
            coco['images'].append({'id': i, 'file_name': name, 'width': w, 'height': h, 'country': country})
            for box in boxes:
                coco['annotations'].append({'id': len(coco['annotations']) + 1, 'image_id': i,
                    'category_id': 1, 'bbox': box, 'area': box[2] * box[3], 'iscrowd': 0})
            c = stats['countries'].setdefault(country, dict(images=0, boxes=0, positives=0, negatives=0))
            c['images'] += 1
            c['boxes'] += len(boxes)
            c['positives' if boxes else 'negatives'] += 1
        (ann / f'{split}.json').write_text(json.dumps(coco))
        stats['splits'][split] = {'images': len(records), 'boxes': len(coco['annotations'])}
    (output / 'dataset_stats.json').write_text(json.dumps(stats, indent=2) + '\n')
    return stats


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path)
    p.add_argument('--archive', type=Path, default=Path('RDD2022.zip'))
    p.add_argument('--output', type=Path, default=Path('ml/data'))
    p.add_argument('--pins', type=Path, default=HERE / 'pins.json')
    p.add_argument('--extra', type=Path)
    args = p.parse_args()
    pins = json.loads(args.pins.read_text())
    digest = None
    if not args.root:
        if not args.archive.exists():
            print('Downloading official 13.3 GB RDD2022 archive on Colab.', flush=True)
            tmp = args.archive.with_suffix('.partial')
            urllib.request.urlretrieve(pins['rdd2022_url'], tmp)
            tmp.replace(args.archive)
        digest = verify_archive(args.archive, args.pins)
        args.root = args.output / 'rdd_source'
        extract(args.archive, args.root)
    stats = prepare(args.root, args.output, pins['seed'], digest, args.extra)
    (HERE / 'dataset_stats.json').write_text(json.dumps(stats, indent=2) + '\n')
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
