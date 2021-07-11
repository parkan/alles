// algorithms.c
// FM2 and partial synths that involve combinations of oscillators
#include "amy.h"


// Thank you MFSA for the DX7 op structure , borrowed here \/ \/ \/ 
enum FmOperatorFlags {
    OUT_BUS_ONE = 1 << 0,
    OUT_BUS_TWO = 1 << 1,
    OUT_BUS_ADD = 1 << 2,
    // there is no 1 << 3
    IN_BUS_ONE = 1 << 4,
    IN_BUS_TWO = 1 << 5,
    FB_IN = 1 << 6,
    FB_OUT = 1 << 7
};
struct FmAlgorithm { uint8_t ops[6]; };
struct FmAlgorithm algorithms[32] = {
    // 6     5     4     3     2      1   
    { { 0xc1, 0x11, 0x11, 0x14, 0x01, 0x14 } }, // 1
    { { 0x01, 0x11, 0x11, 0x14, 0xc1, 0x14 } }, // 2
    { { 0xc1, 0x11, 0x14, 0x01, 0x11, 0x14 } }, // 3
    { { 0x41, 0x11, 0x94, 0x01, 0x11, 0x14 } }, // 4
    { { 0xc1, 0x14, 0x01, 0x14, 0x01, 0x14 } }, // 5
    { { 0x41, 0x94, 0x01, 0x14, 0x01, 0x14 } }, // 6
    { { 0xc1, 0x11, 0x05, 0x14, 0x01, 0x14 } }, // 7
    { { 0x01, 0x11, 0xc5, 0x14, 0x01, 0x14 } }, // 8
    { { 0x01, 0x11, 0x05, 0x14, 0xc1, 0x14 } }, // 9
    { { 0x01, 0x05, 0x14, 0xc1, 0x11, 0x14 } }, // 10
    { { 0xc1, 0x05, 0x14, 0x01, 0x11, 0x14 } }, // 11
    { { 0x01, 0x05, 0x05, 0x14, 0xc1, 0x14 } }, // 12
    { { 0xc1, 0x05, 0x05, 0x14, 0x01, 0x14 } }, // 13
    { { 0xc1, 0x05, 0x11, 0x14, 0x01, 0x14 } }, // 14
    { { 0x01, 0x05, 0x11, 0x14, 0xc1, 0x14 } }, // 15
    { { 0xc1, 0x11, 0x02, 0x25, 0x05, 0x14 } }, // 16
    { { 0x01, 0x11, 0x02, 0x25, 0xc5, 0x14 } }, // 17
    { { 0x01, 0x11, 0x11, 0xc5, 0x05, 0x14 } }, // 18
    { { 0xc1, 0x14, 0x14, 0x01, 0x11, 0x14 } }, // 19
    { { 0x01, 0x05, 0x14, 0xc1, 0x14, 0x14 } }, // 20
    { { 0x01, 0x14, 0x14, 0xc1, 0x14, 0x14 } }, // 21
    { { 0xc1, 0x14, 0x14, 0x14, 0x01, 0x14 } }, // 22
    { { 0xc1, 0x14, 0x14, 0x01, 0x14, 0x04 } }, // 23
    { { 0xc1, 0x14, 0x14, 0x14, 0x04, 0x04 } }, // 24
    { { 0xc1, 0x14, 0x14, 0x04, 0x04, 0x04 } }, // 25
    { { 0xc1, 0x05, 0x14, 0x01, 0x14, 0x04 } }, // 26
    { { 0x01, 0x05, 0x14, 0xc1, 0x14, 0x04 } }, // 27
    { { 0x04, 0xc1, 0x11, 0x14, 0x01, 0x14 } }, // 28
    { { 0xc1, 0x14, 0x01, 0x14, 0x04, 0x04 } }, // 29
    { { 0x04, 0xc1, 0x11, 0x14, 0x04, 0x04 } }, // 30
    { { 0xc1, 0x14, 0x04, 0x04, 0x04, 0x04 } }, // 31
    { { 0xc4, 0x04, 0x04, 0x04, 0x04, 0x04 } }, // 32
};
// End of MSFA stuff

float zeros[BLOCK_SIZE];
float partial_coeffs[5];
float partial_delay[2] = {0,0};


// a = 0
void zero(float *a) {
    for(uint16_t i=0;i<BLOCK_SIZE;i++) {
        a[i] = 0;
    }
}


// b = a + b
void add(float *a, float*b) {
    for(uint16_t i=0;i<BLOCK_SIZE;i++) {
        b[i] = (a[i] + b[i]);
    }
}

void render_mod(float *in, float*out, uint8_t osc, float feedback_level, uint8_t algo_osc) {
    hold_and_modify(osc);
    if(synth[osc].wave == SINE) render_fm_sine(out, osc, in, feedback_level, algo_osc);
}

void note_on_mod(uint8_t osc, uint8_t algo_osc) {
    synth[osc].note_on_clock = total_samples;
    synth[osc].status = IS_ALGO_SOURCE; // to ensure it's rendered
    if(synth[osc].wave==SINE) fm_sine_note_on(osc, algo_osc);
}

void algo_note_off(uint8_t osc) {
    for(uint8_t i=0;i<6;i++) {
        if(synth[osc].algo_source[i] >=0 ) {
            uint8_t o = synth[osc].algo_source[i];
            synth[o].note_on_clock = -1;
            synth[o].note_off_clock = total_samples; 
        }
    }
    // osc note off, start release
    synth[osc].note_on_clock = -1;
    synth[osc].note_off_clock = total_samples;          
}

void algo_note_on(uint8_t osc) {    
    // trigger all the source operator voices
    for(uint8_t i=0;i<6;i++) {
        if(synth[osc].algo_source[i] >=0 ) {
            note_on_mod(synth[osc].algo_source[i], osc);
        }
    }            
}

void algo_init() {
    for(uint16_t i=0;i<BLOCK_SIZE;i++) zeros[i] = 0;
}





void render_algo(float * buf, uint8_t osc) { 
    float scratch[3][BLOCK_SIZE];

    struct FmAlgorithm algo = algorithms[synth[osc].algorithm-1];

    // starts at op 6
    float *in_buf, *out_buf;
    zero(scratch[0]);
    zero(scratch[1]);
    zero(scratch[2]);
    for(uint8_t op=0;op<6;op++) {
        //int8_t opl = (op - 6) * -1; 
        if(synth[osc].algo_source[op] >=0 && synth[synth[osc].algo_source[op]].status == IS_ALGO_SOURCE) {
            float feedback_level = 0;
            in_buf = zeros; // just in case not set elsewhere
            out_buf = scratch[0]; // same

            if(algo.ops[op] & FB_IN) { 
                feedback_level = synth[osc].feedback; 
            } // main algo voice stores feedback, not the op 
            if(algo.ops[op] & IN_BUS_ONE) { 
                in_buf = scratch[0]; 
            }
            if(algo.ops[op] & IN_BUS_TWO) { 
                in_buf = scratch[1]; 
            }
            if(algo.ops[op] & OUT_BUS_ONE) { 
                zero(scratch[0]);
                out_buf = scratch[0]; 
            }
            if(algo.ops[op] & OUT_BUS_TWO) { 
                zero(scratch[1]);
                out_buf = scratch[1]; 
            }
            if(algo.ops[op] & OUT_BUS_ADD) { 
                zero(scratch[2]);
                out_buf = scratch[2]; 
            }
            render_mod(in_buf, out_buf, synth[osc].algo_source[op], feedback_level, osc);
            // TODO -- we could save a buffer here as render adds to out_buf anyway
            if(algo.ops[op] & OUT_BUS_ADD) { 
                // which thing to add to?
                if(algo.ops[op] & OUT_BUS_ONE) {
                    add(scratch[2], scratch[0]); 
                } else if(algo.ops[op] & OUT_BUS_TWO) {
                    add(scratch[2], scratch[1]); 
                } else {
                    add(scratch[2], buf);
                }


            }
        }
    }
    for(uint16_t i=0;i<BLOCK_SIZE;i++) {
        buf[i] = buf[i] * msynth[osc].amp;
    }
}
