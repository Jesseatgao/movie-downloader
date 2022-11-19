## Movie Downloader
A fast movie downloader using Aria2

### Supported sites
* Tencent Video
* m1905

### Third-party Dependencies
* [Aria2](https://github.com/Jesseatgao/aria2-patched-static-build)
    * For Windows:
    
        i686 32-bit version:
    
        https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-i686-win.zip
        
        x86_64 64-bit version:
        
        https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-x86_64-win.zip
    * For Linux:
    
        i686 32-bit version:
        
        https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-i686-linux.tar.xz

        x86_64 64-bit version:
        
        https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-x86_64-linux.tar.xz
        
* [FFmpeg](https://ffmpeg.org/download.html)
    * For Windows:
    
        i686 32-bit version:
    
        https://www.videohelp.com/download/ffmpeg-4.2.2-win32-static.zip
        
        x86_64 64-bit version:
        
        https://www.videohelp.com/download/ffmpeg-4.2.2-win64-static.zip
    * For Linux:
    
        i686 32-bit version:
        
        https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-i686-static.tar.xz

        x86_64 64-bit version:
        
        https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-amd64-static.tar.xz
        
* [MKVToolnix(mkvmerge)](https://github.com/Jesseatgao/MKVToolNix-static-builds)
    * For Windows:
    
        i686 32-bit version:
    
        https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-i686-win.zip
        
        x86_64 64-bit version:
        
        https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-x86_64-win.zip
    * For Linux:
    
        i686 32-bit version:
        
        https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-i686-linux.tar.xz

        x86_64 64-bit version:
        
        https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-x86_64-linux.tar.xz
        
* [node](https://nodejs.org)
    * For Windows:
    
        i686 32-bit version:
    
        https://nodejs.org/dist/v16.15.0/node-v16.15.0-win-x86.zip
        
        x86_64 64-bit version:
        
        https://nodejs.org/dist/v16.15.0/node-v16.15.0-win-x64.zip
    * For Linux:
    
        i686 32-bit version:
        
        https://unofficial-builds.nodejs.org/download/release/v16.15.0/node-v16.15.0-linux-x86.tar.xz

        x86_64 64-bit version:
        
        https://nodejs.org/dist/v16.15.0/node-v16.15.0-linux-x64.tar.xz
        
* [ckey](https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208)
    * For Windows & Linux:
    
        https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208

### Installation
Step 1: install core parsing modules
* via PyPI

    `$ pip install movie-downloader`

* from within source directory locally

    `$ pip install .`

Step 2: get and install third-party dependency programs
* Automatically

  `$ mdl_3rd_parties [--proxy {http|socks5}://[user:password@]host:port]`

* Manually

  Download, unzip and extract `aria2`, `ffmpeg`, `mkvmerge`, `node` and `ckey` into the directory
 `third_parties/aria2/`, `third_parties/ffmpeg/`, `third_parties/mkvtoolnix/`, `third_parties/node/` and `third_parties/ckey/`
 according to the target platform, respectively.

### Usage
```
mdl [-h] [-D DIR] [-d {uhd,fhd,shd,hd,sd}] [-p PROXY] [--QQVideo-no-logo {True,False}]
    [-A ARIA2C] [-F FFMPEG] [-M MKVMERGE] [-N NODE] [-L {debug,info,warning,error,critical}]
    url [url ...] [--playlist-items PLAYLIST_ITEMS]
```

**Description**:

`-D DIR`: specify _DIR_ to save downloaded videos.

`-d {uhd,fhd,shd,hd,sd}`: specify the definition of the video to download. `uhd,fhd,shd,hd,sd` correspond to `4K, 1080P, 720P, 480P, 270P` respectively.

`-p PROXY`: specify the proxy server _PROXY_ (in the form of `http://[user:password@]host:port`)
    used to get web pages or download videos (if configured in `conf/dlops.conf`).

`--QQVideo-no-logo {True,False}`: indicate whether we're trying to download no-watermarked QQVideos or not.

`-A ARIA2C`: specify the absolute path to `aria2c` executable, which takes precedence over the configuration in `conf/misc.conf`
    and the hard-coded fallback path `third_parties/aria2/aria2c[.exe]`.

`-F FFMPEG`: specify the absolute path to `ffmpeg` executable, which takes precedence over the configuration in `conf/misc.conf`
    and the hard-coded fallback path `third_parties/ffmpeg/ffmpeg[.exe]`.

`-M MKVMERGE`: specify the absolute path to `mkvmerge` executable, which takes precedence over the configuration in `conf/misc.conf`
    and the hard-coded fallback path `third_parties/mkvtoolnix/mkvmerge[.exe]`.

`-N NODE`: specify the absolute path to `node` executable, which takes precedence over the configuration in `conf/misc.conf`
    and the hard-coded fallback path `third_parties/node/node[.exe]`.

`-L {debug,info,warning,error,critical}`: specify logging level.

`url [url ...]`: one or more web page URLs of video episodes, cover and playlist.

`--playlist-items PLAYLIST_ITEMS`: desired episode indices in a playlist separated by commas, while the playlists are separated by semicolons,
    e.g. `--playlist-items 1,2,5-10`, `--playlist-items 1,2,5-10;3-`, and `--playlist-items 1,2,5-10;;-20`.

### Credits
* [**youtube-dl** - an App to download videos from YouTube and other video platforms](https://github.com/ytdl-org/youtube-dl)
* [**YouKuDownLoader** - a video downloader focused on China mainland video sites](https://github.com/SeaHOH/ykdl)
* [**iqiyi-parser** - a video downloader for iqiyi, bilibili and TencentVideo sites](https://github.com/ZSAIm/iqiyi-parser)