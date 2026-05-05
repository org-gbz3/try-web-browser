# Cheap-Browser

- [著者ページ](https://browser.engineering/)
- [コード解説（GitHub）](https://github.com/negibokken/web-browser-engineering-step-by-step)

## ローカルの HTML ファイルをホストする

```
python -m http.server 8000 --directory www
```

## 11章

### Skia インストール

```
$ python -m pip install skia-python pysdl2 pysdl2-dll PyOpenGL
...
Installing collected packages: pysdl2-dll, pysdl2, PyOpenGL, pybind11, numpy, skia-python
Successfully installed PyOpenGL-3.1.10 numpy-2.4.4 pybind11-3.0.4 pysdl2-0.9.17 pysdl2-dll-2.32.0 skia-python-144.0.post2
```

### ヘッドレス環境（Dev Container等）で仮想ディスプレイ経由で動かす

```bash
sudo apt-get install -y xvfb libegl1-mesa libgl1-mesa-glx

# 仮想ディスプレイを起動してから実行
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99
python main.py
```
