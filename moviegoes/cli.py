import numpy as np
import pandas as pd
import xarray as xr
from matplotlib import colormaps
from PIL import Image
import click

import argparse, os
from pathlib import Path
import subprocess
import multiprocessing
from itertools import repeat

import s3fs
from goes2go.data import goes_timerange
from goes2go.accessors import fieldOfViewAccessor as fov

def sizeof_fmt(num, suffix="B"):
    '''turn number of bytes to human-readable size'''
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

def plot(filepath,frame_nums,render_folder,ref,res=(1920,1080),data_range=[0,14],cmap='PuRd'):
    '''save image of radiance from data file'''
    try:
        ds = xr.open_dataset(filepath,drop_variables=set(ref).difference(['Rad']))
        da = ds['Rad']
        i  = frame_nums[str(filepath)]
        #stackoverflow.com/questions/10965417
        #convert 2D numpy array into image with PIL
        im = Image.fromarray(colormaps[cmap](da/data_range[-1], bytes=True))
        #stackoverflow.com/questions/23460275
        #upsample
        #im = im.resize(2*np.array(da.shape), resample=Image.BOX)
        im = im.resize(res, resample=Image.BOX)
        im.save(render_folder/f'img{i:04d}.png')
        del ds, da, i, im
        return 0
    except OSError:
        return 1
    #gc.collect(generation=2)

def create_case_name(domain,satellite,start_time,num_hours,bands,cmap,res,scale):
    '''create case name'''
    name = {'F':'disk','C':'conus','M':'meso'}[domain]+'-'
    name += {'WEST':'w','EAST':'e'}[satellite]+'_'
    name += pd.to_datetime(start_time).strftime('%Y-%m-%d_T%H')+'_'
    name += f"{num_hours:.0f}hrs_"
    name += f"chan{bands}_"
    name += cmap if len(cmap)<4 else cmap[:4]
    name += f"_{res}{scale:.1f}x"
    return name

def get_max(f,ref,name='Rad'):
    '''quick open dataset and get max value of variable'''
    return xr.open_dataset(f,drop_variables=set(ref).difference([name]))[name].max().item(0)

def get_data_range(df,netcdf_dir,n_draws=20):
    '''guess a consistent colorbar range - checking every file is too slow'''
    pulls   = np.random.randint(0,len(df),n_draws)
    files   = [netcdf_dir/df['file'][i] for i in pulls]
    ref     = xr.open_dataset(netcdf_dir/df['file'][0])
    maxes   = [get_max(file,ref) for file in files]
    data_range = [0, max(maxes)]
    return ref, data_range

def log_order_size(df, max_order_size=20e9): #bytes
    '''check size of query and print to console'''
    fs    = s3fs.S3FileSystem(anon=True)
    kinds = df['file'].apply(lambda s: '_'.join(s.split('/')[-1].split('_')[:2]))
    kinds, locs, which, counts = np.unique(kinds,return_counts=True,
                                           return_inverse=True,return_index=True)
    sizes = np.array([fs.du(df['file'][i]) for i in locs])
    size  = np.sum(sizes*counts)
    assert size<max_order_size, f'Order of {sizeof_fmt(size)} above {sizeof_fmt(max_order_size)} max'
    print(f'✈️  Order of {len(df)} files is {sizeof_fmt(size)} of data')
    return size

def log_cache_size(netcdf_dir, max_netcdf_size = 22e9): #bytes
    '''check size of local cache and print to console'''
    netcdf_size = sum(f.stat().st_size for f in netcdf_dir.glob('**/*') if f.is_file())
    assert netcdf_size<max_netcdf_size, f'Archive is {sizeof_fmt(netcdf_size)}, larger than the max of {sizeof_fmt(max_netcdf_size)}. Cannot download more data'
    print(f'💿 Local cache of netcdf files is {sizeof_fmt(netcdf_size)}')
    return netcdf_size

def calculate_resolution(res,scale,df,netcdf_dir):
    '''calculate output video resolution'''
    resolutions = {
        '480p': [720, 480],
        '540p': [960, 540],
        '720p': [1280, 720],
        '1080p': [1920, 1080],
        '1440p': [2560, 1440],
        '2160p': [3840, 2160],
        '4k': [4096, 2160],
        '5k': [5120, 2880],
        '8k': [7680, 4320]
    }
    if res != 'native':
        res = np.array(resolutions[res])
    else:
        ds  = xr.open_dataset(netcdf_dir/df['file'][0])
        res = np.array(ds['Rad'].shape)
    res = np.array(res*scale,dtype=int)
    return res

@click.command()
@click.option("--cache","netcdf_dir",help="where to cache netcdf files from aws",default=Path('~/Documents/noaa_data/goes').expanduser(),type=click.Path(path_type=Path,file_okay=False,dir_okay=True,writable=True))
@click.option("--output","render_dir",help="where to save output video",default=Path('~/Documents/goes_animations').expanduser(),type=click.Path(path_type=Path,file_okay=False,dir_okay=True,writable=True))
@click.option("--start","start_time",help="start time of movie (YYYY-MM-DD HH:MM)", default='2024-01-01 00:00',type=str)
@click.option("--hours","num_hours",help="hours to run", default=1.0,type=float)
@click.option("--sat","satellite",help="satellite slot", default='EAST', type=click.Choice(['EAST','WEST'], case_sensitive=False))
@click.option("--domain",help="scan domain. F: full disk, C: CONUS, M: mesoscale", default='M', type=click.Choice(['F','C','M'], case_sensitive=False))
@click.option("--band","bands",help="frequency band", default=2, type=click.IntRange(1,16))
@click.option("--colors","cmap",help="colormap chosen from matplotlib.org/stable/users/explain/colors/colormaps.html", default='twilight_shifted', type=str)
@click.option("--fps",help="video frames per second",default=12,type=int)
@click.option("--scale",help="factor to scale data resolution for video",default=1,type=float)
@click.option("--res",help="output video resolution", default='1080p',type=click.Choice(['480p','540p','720p','1080p','2k','1440p','2160p','4k','native'], case_sensitive=False))
def cli(netcdf_dir,render_dir,start_time,num_hours,satellite,domain,bands,cmap,fps,scale,res):
    '''Order GOES data and export it as a .mp4 animation'''

    ###############################
    ### PARSE ARGS + ORDER DATA ###
    ###############################

    #defaults
    n_cores = multiprocessing.cpu_count() #local cpu cores
    
    #parse parameters
    name = create_case_name(domain,satellite,start_time,num_hours,bands,cmap,res,scale)
    end_time = pd.to_datetime(start_time)+pd.Timedelta(hours=num_hours)
    end_time = end_time.strftime('%Y-%m-%d %H:%M')
    query = {'start': start_time, 'end': end_time, 'satellite': satellite, 
             'domain': domain, 'bands': bands}

    #check that data order and local cache aren't too big
    df = goes_timerange(**query,product='ABI-L1b-Rad',return_as='filelist', download=False)
    order_size = log_order_size(df)
    cache_size = log_cache_size(netcdf_dir)
    
    #download files
    df = goes_timerange(**query, product='ABI-L1b-Rad', 
                        return_as='filelist', download=True,
                        overwrite=False, save_dir=netcdf_dir)
    #parse data-dependent parameters
    ref, data_range = get_data_range(df, netcdf_dir)
    res = calculate_resolution(res,scale,df,netcdf_dir)

    #####################
    ### PLOT + RENDER ###
    #####################

    #handle M1 and M2 domains separately
    kinds = df['file'].apply(lambda s: '_'.join(s.split('/')[-1].split('_')[:2]))
    kinds, locs, which, counts = np.unique(kinds,return_counts=True,
                                           return_inverse=True,return_index=True)
    
    #plot frames and save to disk
    for i, kind in enumerate(kinds):
        #get files with the same scan domain
        files     = netcdf_dir/df['file'][which==i]

        #make output directory, or if it exists but is empty
        name_i = f'{name}_pt{i}'
        try:
            (render_dir/name_i).mkdir()
        except FileExistsError:
            try:
                (render_dir/name_i).rmdir()
                (render_dir/name_i).mkdir()
            except:
                print(f'{render_dir/name_i} not empty! Skipping...')
                continue

        frame_nums = {str(filepath):i for i,filepath in enumerate(files)}
        pool    = multiprocessing.Pool(n_cores-1)
        #parallelize
        #syntax from stackoverflow.com/questions/5442910
        results = pool.starmap(plot,zip(files, repeat(frame_nums), repeat(render_dir/name_i), 
                                        repeat(ref),repeat(res), repeat(data_range),
                                        repeat(cmap)), chunksize=10)
        #close the pool and wait for the work to finish
        pool.close()
        pool.join()
        print(f'🎥 finished part {i+1} of {len(kinds)}: {sum(results)}/{len(files)} frames failed.')

    #transcode videos
    for i, kind in enumerate(kinds):
        name_i = f'{name}_pt{i}'
        opts = '-crf 18 -pix_fmt yuv420p -f mp4 -vcodec libx264 -vf "pad=ceil(iw/2)*2:ceil(ih/2)*2"'
        subprocess.call(
            f"ffmpeg -framerate {fps} -i {render_dir/name_i}/img%04d.png {opts} {render_dir/name_i}.mp4", 
            shell=True)
    
    #delete folders of pngs
    for i, kind in enumerate(kinds):
        name_i = f'{name}_pt{i}'
        folder = render_dir/name_i
        files = df['file'][which==i]
        for j in range(len(files)):
            (folder/f'img{j:04d}.png').unlink(missing_ok=True)
        folder.rmdir()

if __name__ == "__main__":
    cli()
