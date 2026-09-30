import glob,subprocess,sys,imageio_ffmpeg
ff=imageio_ffmpeg.get_ffmpeg_exe()
fs=sorted(glob.glob("stills/*.jpg"),key=lambda p:float(p.split('/')[-1][:-4]))
for k in range(0,len(fs),9):
    grp=fs[k:k+9]; n=len(grp); args=[ff,'-y','-loglevel','error']
    for f in grp: args+=['-i',f]
    fc=''.join(f'[{i}]scale=960:540[s{i}];' for i in range(n))+''.join(f'[s{i}]' for i in range(n))+f'xstack=inputs={n}:layout='+'|'.join(f'{(i%3)*960}_{(i//3)*540}' for i in range(n))+':fill=black[o]'
    subprocess.run(args+['-filter_complex',fc,'-map','[o]','-q:v','4',f'sheet{k//9}.jpg'],check=True)
