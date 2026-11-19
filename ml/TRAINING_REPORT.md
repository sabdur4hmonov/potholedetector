# TRAIN-001

Holat: xato
Status: failed

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

    ,{"stream_name":"stderr","time":592.236431452,"data":"  \n"}
    ,{"stream_name":"stderr","time":592.2364403,"data":"  × Building wheel for onnx (pyproject.toml) did not run successfully.\n"}
    ,{"stream_name":"stderr","time":592.236444381,"data":"  │ exit code: 1\n"}
    ,{"stream_name":"stderr","time":592.236447408,"data":"  ╰─\u003e No available output.\n"}
    ,{"stream_name":"stderr","time":592.236451079,"data":"  \n"}
    ,{"stream_name":"stderr","time":592.236454293,"data":"  note: This error originates from a subprocess, and is likely not a problem with pip.\n"}
    ,{"stream_name":"stdout","time":592.237056173,"data":"  Building wheel for onnx (pyproject.toml): finished with status 'error'\n"}
    ,{"stream_name":"stderr","time":592.237692394,"data":"  ERROR: Failed building wheel for onnx\n"}
    ,{"stream_name":"stdout","time":592.238185004,"data":"Successfully built numpy pycocotools\n"}
    ,{"stream_name":"stdout","time":592.238512201,"data":"Failed to build onnx\n"}
    ,{"stream_name":"stderr","time":592.239824023,"data":"error: failed-wheel-build-for-install\n"}
    ,{"stream_name":"stderr","time":592.239841103,"data":"\n"}
    ,{"stream_name":"stderr","time":592.239857432,"data":"× Failed to build installable wheels for some pyproject.toml based projects\n"}
    ,{"stream_name":"stderr","time":592.23986459,"data":"╰─\u003e onnx\n"}
    ,{"stream_name":"stderr","time":593.57117824,"data":"Traceback (most recent call last):\n"}
    ,{"stream_name":"stderr","time":593.572180525,"data":"  File \"/kaggle/src/script.py\", line 42, in \u003cmodule\u003e\n"}
    ,{"stream_name":"stderr","time":593.572199835,"data":"    main()\n"}
    ,{"stream_name":"stderr","time":593.572204872,"data":"    ~~~~^^\n"}
    ,{"stream_name":"stderr","time":593.572209708,"data":"  File \"/kaggle/src/script.py\", line 38, in main\n"}
    ,{"stream_name":"stderr","time":593.57221405,"data":"    run(root, TRAIN_COMMIT, started, RUN_BUDGET_SECONDS)\n"}
    ,{"stream_name":"stderr","time":593.572228632,"data":"    ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
    ,{"stream_name":"stderr","time":593.572232072,"data":"  File \"/kaggle/tmp/pothole/ml/kaggle/cloud_run.py\", line 45, in run\n"}
    ,{"stream_name":"stderr","time":593.572235366,"data":"    install_yolox(root, checkout)\n"}
    ,{"stream_name":"stderr","time":593.572242302,"data":"    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^\n"}
    ,{"stream_name":"stderr","time":593.572245743,"data":"  File \"/kaggle/tmp/pothole/ml/runtime_setup.py\", line 15, in install_yolox\n"}
    ,{"stream_name":"stderr","time":593.572249124,"data":"    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(root / 'ml/requirements-colab.txt'),\n"}
    ,{"stream_name":"stderr","time":593.572253322,"data":"    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
    ,{"stream_name":"stderr","time":593.572257254,"data":"                    'setuptools==75.8.0', 'wheel==0.45.1', 'packaging==24.2'], check=True)\n"}
    ,{"stream_name":"stderr","time":593.572261181,"data":"                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
    ,{"stream_name":"stderr","time":593.572264697,"data":"  File \"/usr/lib/python3.13/subprocess.py\", line 578, in run\n"}
    ,{"stream_name":"stderr","time":593.572268321,"data":"    raise CalledProcessError(retcode, process.args,\n"}
    ,{"stream_name":"stderr","time":593.572271725,"data":"                             output=stdout, stderr=stderr)\n"}
    ,{"stream_name":"stderr","time":593.572275445,"data":"subprocess.CalledProcessError: Command '['/usr/bin/python3', '-m', 'pip', 'install', '-r', '/kaggle/tmp/pothole/ml/requirements-colab.txt', 'setuptools==75.8.0', 'wheel==0.45.1', 'packaging==24.2']' returned non-zero exit status 1.\n"}
    ,{"stream_name":"stderr","time":596.147880137,"data":"/usr/local/lib/python3.13/dist-packages/mistune.py:435: SyntaxWarning: invalid escape sequence '\\|'\n"}
    ,{"stream_name":"stderr","time":596.14790825,"data":"  cells[i][c] = re.sub('\\\\\\\\\\|', '|', cell)\n"}
    ,{"stream_name":"stderr","time":596.490749973,"data":"/usr/local/lib/python3.13/dist-packages/nbconvert/filters/filter_links.py:36: SyntaxWarning: invalid escape sequence '\\_'\n"}
    ,{"stream_name":"stderr","time":596.490789871,"data":"  text = re.sub(r'_', '\\_', text) # Escape underscores in display text\n"}
    ,{"stream_name":"stderr","time":597.659649534,"data":"[NbConvertApp] Converting notebook __script__.ipynb to html\n"}
    ,{"stream_name":"stderr","time":598.999897338,"data":"[NbConvertApp] Writing 280579 bytes to __results__.html\n"}
    ]
