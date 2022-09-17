# fm.py
# Some code to try to convert DX7 patches into AMY commands

import amy
import numpy as np
import time

from dataclasses import dataclass
from typing import List

@dataclass
class DX7Operator:
    """Per-operator parameters for DX7 patches."""
    opnum: int = 0
    rates: List[int] = None  # 4
    levels: List[int] = None # 4
    breakpoint: int = 0
    bp_depths: List[int] = None # 2
    bp_curves: List[int] = None # 2
    kbdratescaling: int = 0
    ampmodsens: int = 0
    keyvelsens: int = 0
    ratiotuning: bool = False
    freq_coarse: int = 0
    freq_fine: int = 0
    freq_detune: int = 0
    opamp: int = 0

@dataclass
class DX7Patch:
    """Encapsulates information in a DX7 Patch."""
    ops: List[DX7Operator] = None
    pitch_rates: List[int] = None # 4
    pitch_levels: List[int] = None # 4
    algo: int = 0  # 1-32
    feedback: int = 0
    oscsync: int = 0
    lfospeed: int = 0
    lfodelay: int = 0
    lfopitchmoddepth: int = 0
    lfoampmoddepth: int = 0
    lfosync: int = 0
    lfowaveform: int = 0
    pitchmodsens: int = 0
    transpose: int = 0
    name: str = ""

    @staticmethod
    def from_patch_number(patch_number):
        # returns a patch (as in patches.h) from 
        # default-dx7-patches.bin generated by dx7db, see https://github.com/bwhitman/learnfm
        f = bytes(open("default-dx7-patches.bin", mode="rb").read())
        patch_data = f[patch_number*156:patch_number*156+156]
        return DX7Patch.from_bytestream(bytearray(patch_data))

    @staticmethod
    def from_bytestream(bytestream):
        """Simply reformat the bytestream into parameters."""
        result = DX7Patch()

        bytestream = bytes(bytestream)
        byteno = 0

        def nextbyte(count=1):
            nonlocal byteno
            if count > 1:
                # Return a list.
                return [nextbyte() for _ in range(count)]
            b = bytestream[byteno]
            byteno += 1
            # Return a bare byte.
            return b

        ops = []
        # Starts at op 6
        for i in range(6, 0, -1):
            op = DX7Operator(opnum=i)
            op.rates = nextbyte(4)
            op.levels = nextbyte(4)
            op.breakpoint = nextbyte()
            op.bp_depths = nextbyte(2)
            op.bp_curves = nextbyte(2)
            op.kbdratescaling = nextbyte()
            op.ampmodsens = nextbyte()
            op.keyvelsens = nextbyte()
            op.opamp = nextbyte()
            op.ratiotuning = False if nextbyte() == 1 else True
            op.freq_coarse = nextbyte()
            op.freq_fine = nextbyte()
            op.freq_detune = nextbyte()
            ops.append(op)
        result.ops = ops
        result.pitch_rates = nextbyte(4)
        result.pitch_levels = nextbyte(4)
        result.algo = 1 + nextbyte()
        result.feedback = nextbyte()
        result.oscsync = nextbyte()
        result.lfospeed = nextbyte()
        result.lfodelay = nextbyte()
        result.lfopitchmoddepth = nextbyte()
        result.lfoampmoddepth = nextbyte()
        result.lfosync = nextbyte()
        result.lfowaveform = nextbyte()
        result.pitchmodsens = nextbyte()
        result.transpose = nextbyte()
        result.name =  ''.join(chr(i) for i in nextbyte(10))
        return result

    def get_bytestream(self):
        """Convert a decoded patch dict back to a bytestream."""
        bytestream = []
        for op in self.ops:
            # Assume ordering is right in ops list.
            bytestream.extend(op.rates)
            bytestream.extend(op.levels)
            bytestream.append(op.breakpoint)
            bytestream.extend(op.bp_depths)
            bytestream.extend(op.bp_curves)
            bytestream.append(op.kbdratescaling)
            bytestream.append(op.ampmodsens)
            bytestream.append(op.keyvelsens)
            bytestream.append(op.opamp)
            bytestream.append(0 if op.ratiotuning else 1)
            bytestream.append(op.freq_coarse)
            bytestream.append(op.freq_fine)
            bytestream.append(op.freq_detune)
        bytestream.extend(self.pitch_rates)
        bytestream.extend(self.pitch_levels)
        bytestream.append(self.algo - 1)
        bytestream.append(self.feedback)
        bytestream.append(self.oscsync)
        bytestream.append(self.lfospeed)
        bytestream.append(self.lfodelay)
        bytestream.append(self.lfopitchmoddepth)
        bytestream.append(self.lfoampmoddepth)
        bytestream.append(self.lfosync)
        bytestream.append(self.lfowaveform)
        bytestream.append(self.pitchmodsens)
        bytestream.append(self.transpose)
        bytestream.extend(ord(c) for c in self.name)
        return bytes(bytestream)

@dataclass
class AMYOscillator:
    op_num: int = 0
    amp_levels: List[float] = None
    amp_times: List[float] = None
    op_amp: float = 0
    ampmodsens: float = 0
    frequency: float = 0
    freq_is_ratio: bool = False

    @staticmethod
    def from_dx7_op(op):
        result = AMYOscillator()
        result.op_num = op.opnum
        result.amp_levels, result.amp_times = eg_to_bp(op.rates, op.levels)
        result.op_amp = 2 * dx7level_to_linear(op.opamp)
        if op.ratiotuning:
            result.frequency = coarse_fine_ratio(op.freq_coarse, op.freq_fine, op.freq_detune)
            result.freq_is_ratio = True
        else:
            result.frequency = coarse_fine_fixed_hz(op.freq_coarse, op.freq_fine, op.freq_detune)
            result.freq_is_ratio = False
        result.ampmodsens = float(op.ampmodsens)  # Don't know scaling, just 0/nonzero.
        return result
    
@dataclass
class AMYPatch:
    oscs: List[AMYOscillator] = None
    pitch_levels: List[float] = None
    pitch_times: List[float] = None
    algo: int = 0
    feedback: float = 0
    lfo_freq: float = 0
    lfo_delay: float = 0
    lfo_pitchmoddepth: float = 0
    lfo_ampmoddepth: float = 0
    lfo_waveform: int = 0
    name: str = ""
    exp_type: float = amy.TARGET_DX7_EXPONENTIAL
    amp_lfo_amp: float = 0 
    pitch_lfo_amp: float = 0

    @staticmethod
    def from_dx7(dx7_patch):
        result = AMYPatch()
        result.oscs = []
        for op in dx7_patch.ops:
            result.oscs.append(AMYOscillator.from_dx7_op(op))
        result.pitch_levels, result.pitch_times = eg_to_bp_pitch(
            dx7_patch.pitch_rates, dx7_patch.pitch_levels)
        result.algo = dx7_patch.algo
        result.feedback = 0.00125 * (2 ** dx7_patch.feedback)
        result.lfo_freq = lfo_speed_to_hz(dx7_patch.lfospeed)
        result.lfo_delay = dx7_patch.lfodelay
        result.lfo_pitchmoddepth = dx7_patch.lfopitchmoddepth
        result.lfo_ampmoddepth = dx7_patch.lfoampmoddepth
        result.lfo_waveform = lfo_wave(dx7_patch.lfowaveform)
        result.amp_lfo_amp = dx7level_to_linear(result.lfo_ampmoddepth)
        result.pitch_lfo_amp = dx7level_to_linear(result.lfo_pitchmoddepth)

        result.name = dx7_patch.name
        return result
    
    def send_to_AMY(self):
        # Take a FM patch and output AMY commands to set up the patch.
        # Send amy.send(vel=0,osc=6,note=50) after
    
        amy.reset()
        pitch_levels, pitch_times = self.pitch_levels, self.pitch_times
        pitchbp = "%d,%f,%d,%f,%d,%f,%d,%f,%d,%f" % (
            pitch_times[0], pitch_levels[0], pitch_times[1], pitch_levels[1],
            pitch_times[2], pitch_levels[2], pitch_times[3], pitch_levels[3],
            pitch_times[4], pitch_levels[4])
        # Set up each operator.
        last_release_time = 0
        last_release_value = 0
        for i, osc in enumerate(self.oscs):
            amp_levels, amp_times = osc.amp_levels, osc.amp_times
            oscbp = "%d,%f,%d,%f,%d,%f,%d,%f,%d,%f" % (
                amp_times[0], amp_levels[0], amp_times[1], amp_levels[1],
                amp_times[2], amp_levels[2], amp_times[3], amp_levels[3],
                amp_times[4], amp_levels[4])
            oscbpfmt = "%d,%.3f/%d,%.3f/%d,%.3f/%d,%.3f/%d,%.3f" % (
                amp_times[0], amp_levels[0], amp_times[1], amp_levels[1],
                amp_times[2], amp_levels[2], amp_times[3], amp_levels[3],
                amp_times[4], amp_levels[4])
            if(amp_times[4] > last_release_time):
                last_release_time = amp_times[4]
                last_release_value = amp_levels[4]
            print("osc %d (op %d) freq %.2f ratio %d env %s amp %.3f amp_mod %d" % \
                  (i, osc.op_num, osc.frequency, osc.freq_is_ratio, oscbpfmt,
                   osc.op_amp, osc.ampmodsens))

            # Make them all in cosine phase, to be like DX7.  Important for slow oscs
            args = {"osc":i,
                    "bp0_target":amy.TARGET_AMP+amy.TARGET_DX7_EXPONENTIAL,
                    "bp0":oscbp, "amp":osc.op_amp, "phase":0.25}
            if osc.freq_is_ratio:
                args["ratio"] = osc.frequency
            else:
                args["freq"] = osc.frequency
            if(osc.ampmodsens > 0):
                # TODO: we ignore intensity of amp mod sens, just on/off
                args.update({"mod_source": 7, "mod_target":amy.TARGET_AMP})

            # We are _NOT_ updating operators with pitch bp, per dan tuesday 7/5 morning (but not monday 7/4 morning)
            #args.update({"bp1": pitchbp,
            #             "bp1_target": amy.TARGET_FREQ+amy.TARGET_TRUE_EXPONENTIAL})

            amy.send(**args)

        # Set up the amp LFO 
        print("osc 7 amp lfo wave %d freq %f amp %f" % (
            self.lfo_waveform, self.lfo_freq, self.amp_lfo_amp))
        amy.send(osc=7, wave=self.lfo_waveform, freq=self.lfo_freq,
                   amp=self.amp_lfo_amp)

        # and the pitch one
        print("osc 8 pitch lfo wave %d freq %f amp %f" % (
            self.lfo_waveform, self.lfo_freq, self.pitch_lfo_amp))
        amy.send(osc=8, wave=self.lfo_waveform, freq=self.lfo_freq,
                   amp=self.pitch_lfo_amp)

        print("not used: lfo delay %d " % self.lfo_delay)

        ampbp = "0,1,%d,%f" % (last_release_time, last_release_value)
        print("osc 6 (main)  algo %d feedback %f pitchenv %s ampenv %s" % (
            self.algo, self.feedback, pitchbp, ampbp))
        amy.send(osc=6, wave=amy.ALGO, algorithm=self.algo, feedback=self.feedback,
                   algo_source="0,1,2,3,4,5",
                   bp0=ampbp, bp0_target=amy.TARGET_AMP+amy.TARGET_DX7_EXPONENTIAL,
                   bp1=pitchbp, bp1_target=amy.TARGET_FREQ+amy.TARGET_TRUE_EXPONENTIAL,
                   mod_target=amy.TARGET_FREQ, mod_source=8)

def dx7level_to_linear(dx7level):
    """Map the dx7 0..99 levels to linear amplitude."""
    return 2 ** ((dx7level - 99) / 8)

def linear_to_dx7level(linear):
    """Map a linear amplitude to the dx7 0..99 scale."""
    return np.log2(np.maximum(dx7level_to_linear(0), linear)) * 8 + 99
    
def pitchval_to_ratio(pitchval):
    """Map 0..99 DX7 pitch vals (e.g. from pitch_env) into f0 ratios."""
    # Pitch map 0..99 actually becomes -128..127 via a symmetric map with 50->0, linear from 15 to 85, then 
    # quadratic in the remainder.
    pitchsign = -1 + 2*(pitchval >= 50)
    semipitchval = np.abs(pitchval - 50).astype(float)
    # Above (50 + 36), Quadratic to reach 127 at level 99.
    semipitchval += (semipitchval > 36) * (((semipitchval - 34)**2) * 93/225 - semipitchval + 34)
    # DX7 manual states pitchmod range is +/- 4 octaves, so 32 steps/oct sounds right.
    return 2 ** ((pitchsign * semipitchval) / 32)

def ratio_to_pitchval(ratio):
    semipitchval = 32 * np.log2(ratio)
    pitchsign = -1 + 2*(semipitchval >= 0)
    semipitchval = np.abs(semipitchval)
    # Vectorized conditional treatment of outside -36 to 36.
    semipitchval += (semipitchval > 36) * (34 + np.sqrt(np.abs(semipitchval - 34) * (225/93)) - semipitchval)
    return 50 + pitchsign * semipitchval

def calc_loglin_eg_breakpoints(rates, levels, dx7_attacks=True, 
                               rate_double_interval=6, rate_scale=0.5, rate_offset=0.5):
    """Convert the DX7 rates/levels into (time, target) pairs (for amy)"""
    if dx7_attacks:
        level_to_lin_fn = dx7level_to_linear
    else:
        level_to_lin_fn = pitchval_to_ratio
    # This is the part we precompute in fm.py to get breakpoints to send to amy.
    current_level = levels[-1]
    cumulated_time = 0
    breakpoints = [(cumulated_time, level_to_lin_fn(current_level))]

    MIN_LEVEL = 34
    ATTACK_RANGE = 75

    def level_to_attack_time(level, t_const):
        """Return the time at which a paradigmatic DX7 attack envelope will reach a level (0..99 range)"""
        # Return the t0 that solves level = MIN_LEVEL + ATTACK_RANGE * (1 - exp(-t0 / t_const))
        return -t_const * np.log((MIN_LEVEL + ATTACK_RANGE - np.maximum(MIN_LEVEL, level))/ATTACK_RANGE)

    for segment, (rate, target_level) in enumerate(zip(rates, levels)):
        release_segment = (segment == len(rates)-1)
        if dx7_attacks and target_level > current_level:   # Attack segment
            # The attack envelopes L(t) appear to be ~ 34 + 75 * (1 - exp(t / t_const)), starting from L = 34
            # i.e. they are rising exponentials (as in analog ADSR, but here in the log(amp) domain) 
            # with an asymptote at 109 (i.e., 10 higher than the highest possible amp).
            # The time constant depends on the R (rate) parameter, and is well fit by:
            t_const = 0.008 * (2 ** ((65 - rate)/6))
            # Total time for this segment is t1 - t0 where t0 and t1 solve
            # effective_start = 34 + 75 * (1 - np.exp(-t0 / t_const)) = 109 - 75 exp(-t0 / t_c)
            # target_level = 34 + 75 * (1 - np.exp(-t1 / t_const)) = 109 - 75 exp(-t1 / t_c)
            # so t1 - t0 = -t_c * [log((34 + 75 - target_level)/75) - log((34 + 75 - effective_start)/75)]
            effective_start_level = np.maximum(current_level, MIN_LEVEL)
            t0 = level_to_attack_time(effective_start_level, t_const)
            segment_duration = level_to_attack_time(target_level, t_const) - t0
            #print("eff_st=", effective_start_level, "t_c=", t_const, "t0=", t0, "dur=", segment_duration)
            # Now amy's task will be to recover t0 and t_const from (time, target) pairs
        else:
            # Decay segment, or TRUE_EXPONENTIAL attack segment.
            direction = 1 if target_level > current_level else -1
            # "A falling segment takes 3.5 mins"
            # so delta = 99 in 210 seconds -> level_change_per_sec =  0.5
            # I think just offset everything by 0.5, avoids div0.          
            level_change_per_sec = direction*(rate_offset + rate_scale * (2 ** (rate / rate_double_interval)))
            level_difference = target_level - current_level
            # Hack to cover for sustain = 0, release = 0 release segments which look like they should be zero long
            if release_segment and level_difference == 0:
                level_difference = direction * 60  # e.g. from a decayed level of 80 to zero.
                #print("** Goosing release amp")
            segment_duration = level_difference / level_change_per_sec
            #print("lcps=", level_change_per_sec, "dur=", segment_duration)
        cumulated_time += segment_duration
        breakpoints.append((cumulated_time, level_to_lin_fn(target_level)))
        current_level = target_level
    return breakpoints

def eg_to_bp(egrate, eglevel, calc_eg_args={}):
    breakpoints = calc_loglin_eg_breakpoints(egrate, eglevel, **calc_eg_args)
    rates = []
    times = []
    for time, level in breakpoints:
        times.append(int(1000 * time))
        rates.append(level)
    # Fix release time to be relative to 0, not previous
    times[-1] -= times[-2]
    return rates, times

def eg_to_bp_pitch(egrate, eglevel):
    # Additional args to make breakpoint calculation to the right thing for pitch.
    calc_pitch_eg_args = {'dx7_attacks': False, 'rate_double_interval': 20, 'rate_scale': 11, 'rate_offset': -6}
    return eg_to_bp(egrate, eglevel, calc_pitch_eg_args)
    
def coarse_fine_fixed_hz(coarse, fine, detune=7):
    coarse = coarse & 3
    return 10 ** (coarse + (fine + ((detune - 7) / 8)) / 100 )
    
def coarse_fine_ratio(coarse, fine, detune=7):
    coarse = coarse & 31
    if(coarse == 0):
        coarse = 0.5
    return coarse * (1 + (fine + ((detune - 7) / 8)) / 100)

def lfo_speed_to_hz(byte):
    # Measured values from TX802, linear fit by eye
    if byte == 0:
        return 0.064
    if byte <= 64:
        return byte / 6.0
    if byte <= 85:
        return byte - 64.0 * 5.0/6.0
    # Byte > 85
    return 31.67 + (byte - 85.0) * 1.33

def lfo_wave(byte):
    if byte > 5:
        return None
    return [
        amy.TRIANGLE, amy.SAW_DOWN, amy.SAW_UP, 
        amy.PULSE, amy.SINE, amy.NOISE
    ][byte]


# Play a numpy array on an Apple Silicon mac without having to use an external library
# (sounddevice is currently broken on AS macs)
def play_np_array(np_array, samplerate=amy.SAMPLE_RATE):
    import wave, tempfile , os, struct
    tf = tempfile.NamedTemporaryFile()
    obj = wave.open(tf,'wb')
    obj.setnchannels(1) # mono
    obj.setsampwidth(2)
    obj.setframerate(samplerate)
    for i in range(np_array.shape[0]):
        value = int(np_array[i] * 32767.0)
        data = struct.pack('<h', value)
        obj.writeframesraw( data )
    obj.close()
    os.system("afplay " + tf.name)
    tf.close()


#### Header file stuff below

def generate_fm_header():
    # given a list of patch numbers, output a fm.h
    all_patches = []
    ids = []
    for patch_num in range(1024):
        ids.append(patch_num)
        p = AMYPatch.from_dx7(DX7Patch.from_patch_number(patch_num))
        all_patches.append(p)
    pitch_fix = 0
    amp_fix = 0
    out = open("src/fm.h", "w")
    out.write("// Automatically generated by fm.generate_fm_header()\n#ifndef __FM_H\n#define __FM_H\n#define ALGO_PATCHES %d\n" % (len(all_patches)))
    out.write("const algorithms_parameters_t fm_patches[ALGO_PATCHES] = {\n")
    for idx, p in enumerate(all_patches):
        for x in range(5):
            # We can't store envelope times in ms greater than an uint16 (65 seconds). Rare
            if(p.pitch_times[x] > 65535):
                #print("patch %d pitch times %d is %d" % ( idx, x, p.pitch_times[x]))
                p.pitch_times[x] = 65535
                pitch_fix += 1
        out.write("\t{ %d, %f, {%f, %f, %f, %f, %f}, {%d, %d, %d, %d, %d}, %f, %d, %f, %f, {\n" % (
            p.algo, p.feedback,
            p.pitch_levels[0], p.pitch_levels[1], p.pitch_levels[2], p.pitch_levels[3], p.pitch_levels[4], 
            p.pitch_times[0], p.pitch_times[1], p.pitch_times[2], p.pitch_times[3], p.pitch_times[4],
            p.lfo_freq, p.lfo_waveform, p.amp_lfo_amp, p.pitch_lfo_amp))
        for i, osc in enumerate(p.oscs):
            if osc.ampmodsens > 0:
                lfo_target = amy.TARGET_AMP
            else:
                lfo_target = 0
            if osc.freq_is_ratio:
                ratio = osc.frequency
                frequency = -1
            else:
                ratio = -1
                frequency = osc.frequency
            for x in range(5):
                # We can't store envelope times in ms greater than an uint16 (65 seconds). Rare
                if(osc.amp_times[x] > 65535):
                    #print("patch %d osc %d amp times %d is %d" %(idx, i , x, osc.amp_times[x]))
                    osc.amp_times[x] = 65535
                    amp_fix += 1

            out.write("\t\t\t{%f, %f, %f, {%f, %f, %f, %f, %f}, {%d, %d, %d, %d, %d}, %d}, /* op %d */\n" % (
                frequency, ratio, osc.op_amp,
                osc.amp_levels[0], osc.amp_levels[1], osc.amp_levels[2], osc.amp_levels[3], osc.amp_levels[4], 
                osc.amp_times[0], osc.amp_times[1], osc.amp_times[2], osc.amp_times[3], osc.amp_times[4],
                lfo_target, 6 - i))
        out.write("\t\t},\n\t}, /* %s (%d) */ \n" % (p.name, ids[idx]))
    out.write("};\n#endif // __FM_H\n")
    out.close()
    print("pitch fixed: %d. amp fixed: %d" % (pitch_fix, amp_fix))



