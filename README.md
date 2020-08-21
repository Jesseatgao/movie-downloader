## Movie Downloader
A fast movie downloader using Aria2

### Supported sites
* Tencent Video
* m1905

### Third-party Dependencies
* [Aria2](https://github.com/Jesseatgao/aria2-patched-static-build)
    * For Windows:
    
        i686 32-bit version:
    
        https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux/aria2-i686-win.zip
        
        x86_64 64-bit version:
        
        https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux/aria2-x86_64-win.zip
    * For Linux:
    
        i686 32-bit version:
        
        https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux/aria2-i686-linux.tar.xz

        x86_64 64-bit version:
        
        https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux/aria2-x86_64-linux.tar.xz
        
* [FFmpeg](https://ffmpeg.org/download.html)
    * For Windows:
    
        i686 32-bit version:
    
        https://ffmpeg.zeranoe.com/builds/win32/static/ffmpeg-4.2.2-win32-static.zip
        
        x86_64 64-bit version:
        
        https://ffmpeg.zeranoe.com/builds/win64/static/ffmpeg-4.2.2-win64-static.zip
    * For Linux:
    
        i686 32-bit version:
        
        https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-i686-static.tar.xz

        x86_64 64-bit version:
        
        https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-amd64-static.tar.xz
        
* [MKVToolnix(mkvmerge)](https://github.com/Jesseatgao/MKVToolNix-static-builds)
    * For Windows:
    
        i686 32-bit version:
    
        https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v47.0.0-mingw-w64-win32v1.0/mkvtoolnix-i686-win.zip
        
        x86_64 64-bit version:
        
        https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v47.0.0-mingw-w64-win32v1.0/mkvtoolnix-x86_64-win.zip
    * For Linux:
    
        i686 32-bit version:
        
        https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v47.0.0-mingw-w64-win32v1.0/mkvtoolnix-i686-linux.tar.xz

        x86_64 64-bit version:
        
        https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v47.0.0-mingw-w64-win32v1.0/mkvtoolnix-x86_64-linux.tar.xz        

### Installation
Step 1: install core parsing modules
    
`python setup.py install`

Step 2: get and install third-party dependency programs
* Automatically

  `download_3rd_parties [--proxy {http|socks5}://[user:password@]host:port]`

* Manually

  Download, unzip and extract `aria2c[.exe]`, `ffmpeg[.exe]` and `mkvmerge[.exe]` into the directory
 `third_parties/aria2/`, `third_parties/ffmpeg/`, and `third_parties/mkvtoolnix/` according to the target platform, respectively.

### Usage
`mdl [-h] [-D DIR] [-d {fhd,shd,hd,sd}] [-p PROXY] [--QQVideo-no-logo {True,False}]
     [-A ARIA2C] [-F FFMPEG] [-M MKVMERGE] [-L {debug,info,warning,error,critical}]
     url [url ...]`
     
**Explanation**:

`-D DIR`: specify _DIR_ to save downloaded videos.

`-d {fhd,shd,hd,sd}`: specify the definition of the video to download. `fhd,shd,hd,sd` correspond to `1080P, 720P, 480P, 270P` respectively.

`-p PROXY`: specify the proxy server _PROXY_ (in the form of `{http|socks5}://[user:password@]host:port`)
    used to get web pages or download videos (if configured in `conf/dlops.conf`).
    
`--QQVideo-no-logo {True,False}`: indicate whether we're trying to download no-watermarked QQVideos or not.

`-A ARIA2C`: specify the absolute path to `aria2c` executable, which takes precedence over the configuration in `conf/misc.conf`
    and the hard-coded fallback path `third_parties/aria2/aria2c[.exe]`.

`-F FFMPEG`: specify the absolute path to `ffmpeg` executable, which takes precedence over the configuration in `conf/misc.conf`
    and the hard-coded fallback path `third_parties/ffmpeg/ffmpeg[.exe]`.
    
`-M MKVMERGE`: specify the absolute path to `mkvmerge` executable, which takes precedence over the configuration in `conf/misc.conf`
    and the hard-coded fallback path `third_parties/mkvtoolnix/mkvmerge[.exe]`.
    
`-L {debug,info,warning,error,critical}`: specify logging level.

`url [url ...]`: one or more video web page URLs 