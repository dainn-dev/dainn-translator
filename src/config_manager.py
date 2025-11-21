import configparser
import os
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_file: str = "config/config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file or create default if not exists"""
        # Ensure config directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        if not os.path.exists(self.config_file):
            logger.info("Config file not found, creating default config")
            self.create_default_config()
        else:
            logger.info(f"Loading config from {self.config_file}")
            self.config.read(self.config_file, encoding='utf-8')
            # Ensure all required sections exist
            if 'Global' not in self.config:
                logger.info("Creating Global section")
                self.create_global_section()
            if 'Languages' not in self.config:
                logger.info("Creating Languages section")
                self.create_languages_section()
            if 'Areas' not in self.config:
                logger.info("Creating Areas section")
                self.config['Areas'] = {}
            self.save_config()

    def create_global_section(self) -> None:
        """Create Global section with default values"""
        self.config['Global'] = {
            'source_language': 'en',
            'target_language': 'vi',
            'font_family': 'Consolas',
            'font_size': '14',
            'font_style': 'normal',
            'name_color': '#00ffff',
            'dialogue_color': '#00ff00',
            'background_color': '#000000',
            'opacity': '0.85',
            'credentials_path': '',
            'toggle_hotkey': 'Ctrl+1',
            'auto_pause_enabled': 'False',
            'auto_pause_threshold': '5'
        }

    def create_languages_section(self) -> None:
        """Create Languages section with default values"""
        self.config['Languages'] = {
            'vi': 'Tiếng Việt',
            'en': 'English',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh-cn': 'Chinese (Simplified)',
            'fr': 'French',
            'es': 'Spanish'
        }

    def create_default_config(self) -> None:
        """Create default configuration file"""
        self.create_global_section()
        self.create_languages_section()
        self.config['Areas'] = {}
        self.save_config()

    def save_config(self) -> None:
        """Save current configuration to file"""
        try:
            logger.info(f"Saving config to {self.config_file}")
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logger.info("Config saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {str(e)}", exc_info=True)

    def get_global_setting(self, key: str, default: str = '') -> str:
        """Get a global setting value"""
        return self.config.get('Global', key, fallback=default)

    def set_global_setting(self, key: str, value: str) -> None:
        """Set a global setting value"""
        if 'Global' not in self.config:
            self.create_global_section()
        self.config['Global'][key] = value
        self.save_config()

    def get_background_color(self) -> str:
        """Get background color with fallback"""
        return self.get_global_setting('background_color', '#000000')

    def set_background_color(self, color: str) -> None:
        """Set background color"""
        self.set_global_setting('background_color', color)

    def get_credentials_path(self) -> str:
        """Get Google Cloud credentials path with fallback"""
        return self.get_global_setting('credentials_path', '')

    def set_credentials_path(self, path: str) -> None:
        """Set Google Cloud credentials path"""
        self.set_global_setting('credentials_path', path)

    def get_language_name(self, code: str) -> str:
        """Get language name from code"""
        try:
            return self.config.get('Languages', code, fallback=code)
        except (configparser.NoSectionError, KeyError):
            self.create_languages_section()
            return self.config.get('Languages', code, fallback=code)

    def get_language_code(self, name: str) -> str:
        """Get language code from name"""
        try:
            for code, lang_name in self.config['Languages'].items():
                if lang_name == name:
                    return code
            return name
        except (configparser.NoSectionError, KeyError):
            self.create_languages_section()
            for code, lang_name in self.config['Languages'].items():
                if lang_name == name:
                    return code
            return name

    def get_all_languages(self) -> Dict[str, str]:
        """Get all languages as code:name pairs"""
        try:
            return dict(self.config['Languages'])
        except (configparser.NoSectionError, KeyError):
            self.create_languages_section()
            return dict(self.config['Languages'])

    def get_source_language(self) -> str:
        """Get source language code"""
        return self.get_global_setting('source_language', 'en')

    def get_target_language(self) -> str:
        """Get target language code"""
        return self.get_global_setting('target_language', 'vi')

    def set_source_language(self, code: str) -> None:
        """Set source language code"""
        self.set_global_setting('source_language', code)

    def set_target_language(self, code: str) -> None:
        """Set target language code"""
        self.set_global_setting('target_language', code)

    def get_window_position(self, window_id: str) -> Optional[Tuple[int, int]]:
        """Get window position from config"""
        try:
            x = self.config.getint(window_id, 'x')
            y = self.config.getint(window_id, 'y')
            return (x, y)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None

    def save_window_position(self, window_id: str, x: int, y: int) -> None:
        """Save window position to config"""
        if window_id not in self.config:
            self.config[window_id] = {}
        self.config[window_id]['x'] = str(x)
        self.config[window_id]['y'] = str(y)
        self.save_config()

    def get_all_window_positions(self) -> Dict[str, Tuple[int, int]]:
        """Get all window positions from config"""
        positions = {}
        for section in self.config.sections():
            if section != 'Global' and section != 'Languages' and section != 'Areas':
                try:
                    x = self.config.getint(section, 'x')
                    y = self.config.getint(section, 'y')
                    positions[section] = (x, y)
                except (configparser.NoOptionError, ValueError):
                    continue
        return positions

    def delete_window_position(self, window_id: str) -> None:
        """Delete window position from config"""
        if window_id in self.config:
            del self.config[window_id]
            self.save_config()

    def get_area(self, area_id: str) -> Optional[Dict[str, int]]:
        """Get area configuration"""
        try:
            return {
                'x': self.config.getint('Areas', f'{area_id}_x'),
                'y': self.config.getint('Areas', f'{area_id}_y'),
                'width': self.config.getint('Areas', f'{area_id}_width'),
                'height': self.config.getint('Areas', f'{area_id}_height')
            }
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None

    def save_area(self, area_id: str, x: int, y: int, width: int, height: int) -> None:
        """Save area configuration"""
        try:
            logger.info(f"Saving area {area_id}: x={x}, y={y}, width={width}, height={height}")
            if 'Areas' not in self.config:
                self.config['Areas'] = {}
            self.config['Areas'][f'{area_id}_x'] = str(x)
            self.config['Areas'][f'{area_id}_y'] = str(y)
            self.config['Areas'][f'{area_id}_width'] = str(width)
            self.config['Areas'][f'{area_id}_height'] = str(height)
            self.save_config()
            logger.info(f"Area {area_id} saved successfully")
        except Exception as e:
            logger.error(f"Error saving area {area_id}: {str(e)}", exc_info=True)

    def delete_area(self, area_id: str) -> None:
        """Delete area configuration"""
        if 'Areas' in self.config:
            for key in [f'{area_id}_x', f'{area_id}_y', f'{area_id}_width', f'{area_id}_height']:
                if key in self.config['Areas']:
                    del self.config['Areas'][key]
            self.save_config()

    def get_all_areas(self) -> Dict[str, Dict[str, int]]:
        """Get all area configurations"""
        areas = {}
        try:
            if 'Areas' in self.config:
                area_ids = set()
                for key in self.config['Areas']:
                    area_id = key.split('_')[0]
                    area_ids.add(area_id)
                
                for area_id in area_ids:
                    area = self.get_area(area_id)
                    if area:
                        areas[area_id] = area
                        logger.info(f"Loaded area {area_id}: {area}")
            return areas
        except Exception as e:
            logger.error(f"Error loading areas: {str(e)}", exc_info=True)
            return {}
    
    def get_toggle_hotkey(self) -> str:
        """Get the toggle hotkey"""
        return self.get_global_setting('toggle_hotkey', 'Ctrl+1')
    
    def set_toggle_hotkey(self, hotkey: str) -> None:
        """Set the toggle hotkey"""
        self.set_global_setting('toggle_hotkey', hotkey)
    
    def get_auto_pause_enabled(self) -> bool:
        """Get auto pause enabled status"""
        value = self.get_global_setting('auto_pause_enabled', 'False')
        return value.lower() in ('true', '1', 'yes')
    
    def set_auto_pause_enabled(self, enabled: bool) -> None:
        """Set auto pause enabled status"""
        self.set_global_setting('auto_pause_enabled', str(enabled))
    
    def get_auto_pause_threshold(self) -> int:
        """Get auto pause threshold"""
        try:
            return int(self.get_global_setting('auto_pause_threshold', '5'))
        except ValueError:
            return 5
    
    def set_auto_pause_threshold(self, threshold: int) -> None:
        """Set auto pause threshold"""
        self.set_global_setting('auto_pause_threshold', str(threshold)) 