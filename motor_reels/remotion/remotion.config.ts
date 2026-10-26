import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(100);
Config.setCodec('h264');
Config.setCrf(15);
Config.setOverwriteOutput(true);
Config.setX264Preset('slow');
