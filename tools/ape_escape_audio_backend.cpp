#define MINIAUDIO_IMPLEMENTATION
#include <miniaudio.h>
#include <algorithm>
#include <cmath>
#include <mutex>
#include <string>

/* Native MP3 playback isolated from the launcher model. */
namespace {
ma_engine engine{};
ma_sound sound{};
bool engineReady=false, soundReady=false, paused=false;
ma_uint64 pausedFrame=0;
float volume=0.70f;
std::string lastError;
std::mutex audioMutex;
bool initEngine(){
    if(engineReady)return true;
    const auto r=ma_engine_init(nullptr,&engine);
    if(r!=MA_SUCCESS){lastError="Could not initialize audio output (miniaudio "+std::to_string((int)r)+").";return false;}
    engineReady=true;return true;
}
ma_uint32 sampleRate(){
    if(!soundReady)return 0;
    ma_format format=ma_format_unknown;ma_uint32 channels=0,rate=0;
    return ma_sound_get_data_format(&sound,&format,&channels,&rate,nullptr,0)==MA_SUCCESS?rate:0;
}
}
extern "C" bool ape_escape_audio_play(const char* path){
    std::lock_guard<std::mutex> lock(audioMutex);lastError.clear();
    if(!path||!path[0]){lastError="No track selected.";return false;}
    if(!initEngine())return false;
    if(soundReady){ma_sound_stop(&sound);ma_sound_uninit(&sound);soundReady=false;}
    paused=false;pausedFrame=0;
    const auto r=ma_sound_init_from_file(&engine,path,MA_SOUND_FLAG_STREAM|MA_SOUND_FLAG_NO_SPATIALIZATION,nullptr,nullptr,&sound);
    if(r!=MA_SUCCESS){lastError="Could not decode audio (miniaudio "+std::to_string((int)r)+").";return false;}
    soundReady=true;ma_sound_set_volume(&sound,volume);
    if(ma_sound_start(&sound)!=MA_SUCCESS){lastError="Could not start audio playback.";ma_sound_uninit(&sound);soundReady=false;return false;}
    return true;
}
extern "C" void ape_escape_audio_pause(){
    std::lock_guard<std::mutex> lock(audioMutex);
    if(!soundReady||paused||!ma_sound_is_playing(&sound))return;
    ma_sound_get_cursor_in_pcm_frames(&sound,&pausedFrame);ma_sound_stop(&sound);paused=true;
}
extern "C" void ape_escape_audio_resume(){
    std::lock_guard<std::mutex> lock(audioMutex);
    if(!soundReady||!paused)return;
    if(ma_sound_start(&sound)==MA_SUCCESS){ma_sound_seek_to_pcm_frame(&sound,pausedFrame);paused=false;}
}
extern "C" void ape_escape_audio_stop(){
    std::lock_guard<std::mutex> lock(audioMutex);
    if(!soundReady)return;ma_sound_stop(&sound);ma_sound_seek_to_pcm_frame(&sound,0);pausedFrame=0;paused=false;
}
extern "C" bool ape_escape_audio_is_paused(){std::lock_guard<std::mutex> lock(audioMutex);return soundReady&&paused;}
extern "C" bool ape_escape_audio_has_track(){std::lock_guard<std::mutex> lock(audioMutex);return soundReady;}
extern "C" void ape_escape_audio_set_volume(float v){
    std::lock_guard<std::mutex> lock(audioMutex);volume=std::max(0.0f,std::min(1.0f,v));if(soundReady)ma_sound_set_volume(&sound,volume);
}
extern "C" float ape_escape_audio_get_volume(){std::lock_guard<std::mutex> lock(audioMutex);return volume;}
extern "C" float ape_escape_audio_position(){
    std::lock_guard<std::mutex> lock(audioMutex);if(!soundReady)return 0.0f;
    ma_uint64 frame=paused?pausedFrame:0;if(!paused)ma_sound_get_cursor_in_pcm_frames(&sound,&frame);
    const auto rate=sampleRate();return rate?static_cast<float>(frame)/static_cast<float>(rate):0.0f;
}
extern "C" float ape_escape_audio_duration(){
    std::lock_guard<std::mutex> lock(audioMutex);if(!soundReady)return 0.0f;
    const auto rate=sampleRate();ma_uint64 frames=0;
    if(!rate||ma_sound_get_length_in_pcm_frames(&sound,&frames)!=MA_SUCCESS)return 0.0f;
    return static_cast<float>(frames)/static_cast<float>(rate);
}
extern "C" void ape_escape_audio_seek(float seconds){
    std::lock_guard<std::mutex> lock(audioMutex);if(!soundReady||!std::isfinite(seconds))return;
    const auto rate=sampleRate();ma_uint64 frames=0;float duration=0;
    if(!rate)return;
    if(ma_sound_get_length_in_pcm_frames(&sound,&frames)==MA_SUCCESS)duration=static_cast<float>(frames)/static_cast<float>(rate);
    seconds=std::max(0.0f,std::min(duration,seconds));pausedFrame=static_cast<ma_uint64>(seconds*static_cast<float>(rate));
    ma_sound_seek_to_pcm_frame(&sound,pausedFrame);
}
extern "C" const char* ape_escape_audio_last_error(){return lastError.c_str();}
