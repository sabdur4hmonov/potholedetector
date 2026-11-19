# TRAIN-001

Holat: ishlayapti
Status: running

## Progress / Jarayon

- 2026-11-19 — Kaggle CLI 2.2.5 and its missing six 1.17.0 dependency installed. The account authentication check passed for sardor007. Preparing the private GPU job and offline tests. Model metrics and phone validation are pending.

- 2026-11-19T23:25:57+05:00 — Private GPU run 1 submitted. https://www.kaggle.com/code/sardor007/pothole-yolox-train

- 2026-11-19T23:27:00+05:00 — Kaggle run 1 is running.

- 2026-11-19T23:27:35+05:00 — Kaggle run 1 is running.

- 2026-11-19T23:29:51+05:00 — Server metadata verified: private T4 GPU + internet, pinned commit 8c1c606c676d2c5f29666df6263d522f45461183. PotholeTrainWatch registered every 15 min; scheduler-started tick exited 0. Training/export/model-bearing APK results pending. Reboot requires this Windows user to sign in for local checks.

- 2026-11-19T23:40:56+05:00 — RuntimeError: Kaggle run ended with status error

- 2026-11-20T00:02:51+05:00 — Version 1 stopped in dependency setup before dataset download or training. Kaggle ran Python 3.13. The pinned onnx==1.17.0 was fetched as a source archive and pip failed to build its wheel.

  Kaggle failure evidence for sardor007/pothole-yolox-train/1. KernelWorkerStatus.ERROR

  result.json reason: CalledProcessError: Command '['/usr/bin/python3', '-m', 'pip', 'install', '-r', '/kaggle/tmp/pothole/ml/requirements-colab.txt', 'setuptools==75.8.0', 'wheel==0.45.1', 'packaging==24.2']' returned non-zero exit status 1.

      error: subprocess-exited-with-error

      × Building wheel for onnx (pyproject.toml) did not run successfully.
      │ exit code: 1
      ╰─> No available output.

      note: This error originates from a subprocess, and is likely not a problem with pip.
      Building wheel for onnx (pyproject.toml): finished with status 'error'
      ERROR: Failed building wheel for onnx
    Successfully built numpy pycocotools
    Failed to build onnx
    error: failed-wheel-build-for-install

    × Failed to build installable wheels for some pyproject.toml based projects
    ╰─> onnx
    Traceback (most recent call last):
      File "/kaggle/src/script.py", line 42, in <module>
        main()
        ~~~~^^
      File "/kaggle/src/script.py", line 38, in main
        run(root, TRAIN_COMMIT, started, RUN_BUDGET_SECONDS)
        ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/kaggle/tmp/pothole/ml/kaggle/cloud_run.py", line 45, in run
        install_yolox(root, checkout)
        ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^
      File "/kaggle/tmp/pothole/ml/runtime_setup.py", line 15, in install_yolox
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(root / 'ml/requirements-colab.txt'),
        ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                        'setuptools==75.8.0', 'wheel==0.45.1', 'packaging==24.2'], check=True)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/usr/lib/python3.13/subprocess.py", line 578, in run
        raise CalledProcessError(retcode, process.args,
                                 output=stdout, stderr=stderr)
    subprocess.CalledProcessError: Command '['/usr/bin/python3', '-m', 'pip', 'install', '-r', '/kaggle/tmp/pothole/ml/requirements-colab.txt', 'setuptools==75.8.0', 'wheel==0.45.1', 'packaging==24.2']' returned non-zero exit status 1.
    /usr/local/lib/python3.13/dist-packages/mistune.py:435: SyntaxWarning: invalid escape sequence '\|'
      cells[i][c] = re.sub('\\\\\|', '|', cell)
    /usr/local/lib/python3.13/dist-packages/nbconvert/filters/filter_links.py:36: SyntaxWarning: invalid escape sequence '\_'
      text = re.sub(r'_', '\_', text) # Escape underscores in display text
    [NbConvertApp] Converting notebook __script__.ipynb to html
    [NbConvertApp] Writing 280579 bytes to __results__.html

- 2026-11-20T00:03:42+05:00 — Private smoke version 2 submitted. https://www.kaggle.com/code/sardor007/pothole-yolox-train?version=2

- 2026-11-20T00:06:11+05:00 — Kaggle version 2 is running.

- 2026-11-20T00:15:46+05:00 — Kaggle failure evidence for sardor007/pothole-yolox-train/2. sardor007/pothole-yolox-train/2 has status "KernelWorkerStatus.ERROR"

  result.json reason: ModuleNotFoundError: No module named 'yolox'

              Please be careful with folders in your working directory with the same
              name as your package as they may take precedence during imports.
              ********************************************************************************

      !!
        with strategy, WheelFile(wheel_path, "w") as wheel_obj:
      Created wheel for yolox: filename=yolox-0.3.0-0.editable-cp312-cp312-linux_x86_64.whl size=11814 sha256=e5e239c86be565c4812d03c6f04f9c7858153aebe6cc0074f2f3b0c45c82bb4a
      Stored in directory: /tmp/pip-ephem-wheel-cache-rzl_hee9/wheels/4c/53/d0/18251481f6f93e74b13a4add2a51f7e1ff76c84fa1b7bd1478
    Successfully built yolox
    Installing collected packages: yolox
    Successfully installed yolox-0.3.0
    Downloading RDD2022 to Kaggle temporary disk
    RDD2022 SHA-256: 5d230a2941e8f2ac5fbca1a0faddee393314368dd17f9304effc11ec532845b6
    First-download pin recorded; retain pins.json with the training receipt.
    Prepared full-frame splits: {'train': {'images': 128, 'boxes': 20}, 'val': {'images': 24, 'boxes': 0}, 'test': {'images': 24, 'boxes': 5}}
    Traceback (most recent call last):
      File "/kaggle/tmp/pothole/ml/kaggle/cloud_run.py", line 139, in <module>
        run(args.root, args.commit, args.started, args.budget, args.smoke)
      File "/kaggle/tmp/pothole/ml/kaggle/cloud_run.py", line 98, in run
        from yolox_pothole_exp import Exp
      File "/kaggle/tmp/pothole/ml/yolox_pothole_exp.py", line 6, in <module>
        from yolox.exp import Exp as BaseExp
    ModuleNotFoundError: No module named 'yolox'
    Traceback (most recent call last):
      File "/kaggle/src/script.py", line 74, in <module>
        main()
        ~~~~^^
      File "/kaggle/src/script.py", line 65, in main
        subprocess.run(command, env=env, check=True)
        ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/usr/lib/python3.13/subprocess.py", line 578, in run
        raise CalledProcessError(retcode, process.args,
                                 output=stdout, stderr=stderr)
    subprocess.CalledProcessError: Command '['/kaggle/tmp/train-env/bin/python', '/kaggle/tmp/pothole/ml/kaggle/cloud_run.py', '/kaggle/tmp/pothole', '2afe4b76c3d34d9d9d9674c60b4b20a3caf6e27d', '539.969840549', '2640', '--smoke']' returned non-zero exit status 1.
    /usr/local/lib/python3.13/dist-packages/mistune.py:435: SyntaxWarning: invalid escape sequence '\|'
      cells[i][c] = re.sub('\\\\\|', '|', cell)
    /usr/local/lib/python3.13/dist-packages/nbconvert/filters/filter_links.py:36: SyntaxWarning: invalid escape sequence '\_'
      text = re.sub(r'_', '\_', text) # Escape underscores in display text
    [NbConvertApp] Converting notebook __script__.ipynb to html
    [NbConvertApp] Writing 288335 bytes to __results__.html

- 2026-11-20T00:15:46+05:00 — RuntimeError: Kaggle version 2 stopped. See downloaded failure evidence in the report.

- 2026-11-20T00:16:58+05:00 — Private smoke version 3 submitted. https://www.kaggle.com/code/sardor007/pothole-yolox-train?version=3

- 2026-11-20T00:32:54+05:00 — Kaggle failure evidence for sardor007/pothole-yolox-train/3. sardor007/pothole-yolox-train/3 has status "KernelWorkerStatus.ERROR"

  result.json reason: IndexError: Caught IndexError in DataLoader worker process 0.
Original Traceback (most recent call last):
  File "/kaggle/tmp/train-env/lib/python3.12/site-packages/torch/utils/data/_utils/worker.py", line 349, in _worker_loop
    data = fetcher.fetch(index)  # type: ignore[possibly-undefined]
           ^^^^^^^^^^^^^^^^^^^^
  File "/kaggle/tmp/train-env/lib/python3.12/site-packages/torch/utils/data/_utils/fetch.py", line 52, in fetch
    data = [self.dataset[idx] for idx in possibly_batched_index]
            ~~~~~~~~~~~~^^^^^
  File "/kaggle/tmp/YOLOX/yolox/data/datasets/datasets_wrapper.py", line 117, in wrapper
    self.enable_mosaic = index[0]
                         ~~~~~^^^
IndexError: invalid index of a 0-dim tensor. Use `tensor.item()` in Python or `tensor.item<T>()` in C++ to convert a 0-dim tensor to a number


    ├───────────────────┼────────────────────────┤
    │ test_size         │ (416, 416)             │
    ├───────────────────┼────────────────────────┤
    │ test_conf         │ 0.01                   │
    ├───────────────────┼────────────────────────┤
    │ nmsthre           │ 0.65                   │
    ├───────────────────┼────────────────────────┤
    │ random_size       │ (13, 13)               │
    ├───────────────────┼────────────────────────┤
    │ enable_mosaic     │ False                  │
    ╘═══════════════════╧════════════════════════╛
    2026-11-19 19:28:50 | INFO     | yolox.core.trainer:138 - Model Summary: Params: 0.90M, Gflops: 1.08
    2026-11-19 19:28:50 | INFO     | yolox.data.datasets.coco:63 - loading annotations into memory...
    2026-11-19 19:28:50 | INFO     | yolox.data.datasets.coco:63 - Done (t=0.00s)
    2026-11-19 19:28:50 | INFO     | pycocotools.coco:86 - creating index...
    2026-11-19 19:28:50 | INFO     | pycocotools.coco:86 - index created!
    2026-11-19 19:28:50 | INFO     | yolox.core.trainer:157 - init prefetcher, this might take one minute or less...
    object address  : 0x7b6a85860a60
    object refcount : 4
    object type     : 0x13fe168
    object type name: IndexError
    object repr     : IndexError('Caught IndexError in DataLoader worker process 0.\nOriginal Traceback (most recent call last):\n  File "/kaggle/tmp/train-env/lib/python3.12/site-packages/torch/utils/data/_utils/worker.py", line 349, in _worker_loop\n    data = fetcher.fetch(index)  # type: ignore[possibly-undefined]\n           ^^^^^^^^^^^^^^^^^^^^\n  File "/kaggle/tmp/train-env/lib/python3.12/site-packages/torch/utils/data/_utils/fetch.py", line 52, in fetch\n    data = [self.dataset[idx] for idx in possibly_batched_index]\n            ~~~~~~~~~~~~^^^^^\n  File "/kaggle/tmp/YOLOX/yolox/data/datasets/datasets_wrapper.py", line 117, in wrapper\n    self.enable_mosaic = index[0]\n                         ~~~~~^^^\nIndexError: invalid index of a 0-dim tensor. Use `tensor.item()` in Python or `tensor.item<T>()` in C++ to convert a 0-dim tensor to a number\n')
    lost sys.stderr
    Traceback (most recent call last):
      File "/kaggle/src/script.py", line 74, in <module>
        main()
        ~~~~^^
      File "/kaggle/src/script.py", line 65, in main
        subprocess.run(command, env=env, check=True)
        ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/usr/lib/python3.13/subprocess.py", line 578, in run
        raise CalledProcessError(retcode, process.args,
                                 output=stdout, stderr=stderr)
    subprocess.CalledProcessError: Command '['/kaggle/tmp/train-env/bin/python', '/kaggle/tmp/pothole/ml/kaggle/cloud_run.py', '/kaggle/tmp/pothole', '7213573017623857c3ca29310be4ef0da6bc8ce5', '179.819417069', '2640', '--smoke']' returned non-zero exit status 1.
    /usr/local/lib/python3.13/dist-packages/mistune.py:435: SyntaxWarning: invalid escape sequence '\|'
      cells[i][c] = re.sub('\\\\\|', '|', cell)
    /usr/local/lib/python3.13/dist-packages/nbconvert/filters/filter_links.py:36: SyntaxWarning: invalid escape sequence '\_'
      text = re.sub(r'_', '\_', text) # Escape underscores in display text
    [NbConvertApp] Converting notebook __script__.ipynb to html
    [NbConvertApp] Writing 288335 bytes to __results__.html

- 2026-11-20T00:32:54+05:00 — RuntimeError: Kaggle version 3 stopped. See downloaded failure evidence in the report.

- 2026-11-20T00:38:01+05:00 — Private smoke version 4 submitted. https://www.kaggle.com/code/sardor007/pothole-yolox-train

- 2026-11-20T00:51:38+05:00 — Smoke version 4 passed in 704s. One epoch and 20 ONNX comparisons verified. Submitting full training.

- 2026-11-20T00:51:47+05:00 — Private full training version 5 submitted. https://www.kaggle.com/code/sardor007/pothole-yolox-train

- 2026-11-20T00:53:16+05:00 — Kaggle version 5 is running.

- 2026-11-20T00:55:10+05:00 — Kaggle failure evidence for sardor007/pothole-yolox-train/5. sardor007/pothole-yolox-train/5 has status "KernelWorkerStatus.ERROR"

  result.json reason: HTTPError: HTTP Error 403: Forbidden

      File "/kaggle/tmp/pothole/ml/kaggle/cloud_run.py", line 144, in <module>
        run(args.root, args.commit, args.started, args.budget, args.smoke)
      File "/kaggle/tmp/pothole/ml/kaggle/cloud_run.py", line 74, in run
        with urllib.request.urlopen(pins['rdd2022_url'], timeout=120) as response, archive.open('wb') as target:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/kaggle/tmp/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/urllib/request.py", line 215, in urlopen
        return opener.open(url, data, timeout)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/kaggle/tmp/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/urllib/request.py", line 521, in open
        response = meth(req, response)
                   ^^^^^^^^^^^^^^^^^^^
      File "/kaggle/tmp/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/urllib/request.py", line 630, in http_response
        response = self.parent.error(
                   ^^^^^^^^^^^^^^^^^^
      File "/kaggle/tmp/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/urllib/request.py", line 559, in error
        return self._call_chain(*args)
               ^^^^^^^^^^^^^^^^^^^^^^^
      File "/kaggle/tmp/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/urllib/request.py", line 492, in _call_chain
        result = func(*args)
                 ^^^^^^^^^^^
      File "/kaggle/tmp/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/urllib/request.py", line 639, in http_error_default
        raise HTTPError(req.full_url, code, msg, hdrs, fp)
    urllib.error.HTTPError: HTTP Error 403: Forbidden
    Traceback (most recent call last):
      File "/kaggle/src/script.py", line 74, in <module>
        main()
        ~~~~^^
      File "/kaggle/src/script.py", line 65, in main
        subprocess.run(command, env=env, check=True)
        ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/usr/lib/python3.13/subprocess.py", line 578, in run
        raise CalledProcessError(retcode, process.args,
                                 output=stdout, stderr=stderr)
    subprocess.CalledProcessError: Command '['/kaggle/tmp/train-env/bin/python', '/kaggle/tmp/pothole/ml/kaggle/cloud_run.py', '/kaggle/tmp/pothole', '2508deba2001eb4505b4bc937583935b1c58bb3d', '826.10580939', '43200']' returned non-zero exit status 1.
    /usr/local/lib/python3.13/dist-packages/mistune.py:435: SyntaxWarning: invalid escape sequence '\|'
      cells[i][c] = re.sub('\\\\\|', '|', cell)
    /usr/local/lib/python3.13/dist-packages/nbconvert/filters/filter_links.py:36: SyntaxWarning: invalid escape sequence '\_'
      text = re.sub(r'_', '\_', text) # Escape underscores in display text
    [NbConvertApp] Converting notebook __script__.ipynb to html
    [NbConvertApp] Writing 288337 bytes to __results__.html

- 2026-11-20T00:55:10+05:00 — RuntimeError: Kaggle version 5 stopped. See downloaded failure evidence in the report.

- 2026-11-20T00:57:37+05:00 — Private smoke version 6 submitted. https://www.kaggle.com/code/sardor007/pothole-yolox-train

- 2026-11-20T01:12:36+05:00 — Kaggle version 6 is running.

- 2026-11-20T01:14:46+05:00 — Smoke version 6 passed in 956s. One epoch and 20 ONNX comparisons verified. Submitting full training.

- 2026-11-20T01:14:52+05:00 — Private full training version 7 submitted. https://www.kaggle.com/code/sardor007/pothole-yolox-train

- 2026-11-20T01:27:36+05:00 — Kaggle version 7 is running.

- 2026-11-20T01:31:21+05:00 — Full version 7 live log verified on Tesla T4. "epoch: 1/500, iter: 610/1799" advanced through "epoch: 1/500, iter: 720/1799" at 01:30 +0500. Evidence under ml/kaggle/output/version-7/reconnected-kernel.log. Final metrics, model installation and APK checks pending. https://www.kaggle.com/code/sardor007/pothole-yolox-train/log
