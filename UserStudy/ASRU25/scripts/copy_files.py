import shutil
import os
from pathlib import Path
from tqdm import tqdm
from functools import lru_cache 
import glob

@lru_cache()
def find(files, fid):
    for file in files:
        if fid in file:
            return file


if __name__ == "__main__":
    base_fpath = Path("/mnt/nvme-data1/waris/publications/IS24/User Study/Samples/Verifiability")
    test_set = ["same", "different", "same_anon"]

    audio_files = tuple(glob.glob('/mnt/nvme-data1/waris/CortexCraft/streamingVC/resultsIS24/reconstruction/lite/**/*.wav', recursive=True))
    anon_audio_files = tuple(glob.glob('/mnt/nvme-data1/waris/Anon/VoicePAT/exp/svcv2_anon/**/*.wav', recursive=True))

    for test in tqdm(test_set):
        info = open((base_fpath / test / 'info.txt'), 'r').readlines()
        for fid_pair in info:
            a, b = fid_pair.strip().split('|')
            fpath_a = find(audio_files, a)
            if test == "same_anon":
                fpath_b = find(anon_audio_files, b)
            else:
                fpath_b = find(audio_files, b)
            
            shutil.copy(fpath_a, (base_fpath / test ))
            shutil.copy(fpath_b, (base_fpath / test ))
