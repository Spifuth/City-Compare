"""Plugin system for city-compare.

This module provides a plugin architecture that allows extending city-compare
with custom data sources and scoring functions.

Plugin Types:
    - DataSource: Provide additional data for cities (e.g., crime rates, cost of living)
    - ScoreModifier: Add custom scoring logic

Creating a Plugin:
    1. Create a Python file in ~/.config/city-compare/plugins/
    2. Define a class that inherits from DataSourcePlugin or ScoreModifierPlugin
    3. Register it using the @register_plugin decorator

Example:
    ```python
    from city_compare.plugins import DataSourcePlugin, register_plugin

    @register_plugin
    class CrimeDataPlugin(DataSourcePlugin):
        name = "crime_data"
        description = "Adds crime statistics for cities"

        def get_data(self, city_name: str) -> dict[str, float]:
            # Fetch crime data from API or database
            return {"crime_rate": 45.2, "safety_score": 7.5}
    ```
"""

import importlib.util
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .xdg import get_config_dir


@dataclass
class PluginMetadata:
    """Metadata about a plugin."""

    name: str
    description: str
    version: str
    author: str
    plugin_type: str
    enabled: bool = True


class BasePlugin(ABC):
    """Base class for all plugins."""

    name: str = "unnamed_plugin"
    description: str = "No description"
    version: str = "0.1.0"
    author: str = "Unknown"

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the plugin."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up plugin resources."""
        pass

    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name=self.name,
            description=self.description,
            version=self.version,
            author=self.author,
            plugin_type=self.__class__.__bases__[0].__name__,
        )


class DataSourcePlugin(BasePlugin):
    """
    Base class for data source plugins.

    Data source plugins provide additional data about cities that can be
    used in scoring formulas.
    """

    # Variables this plugin provides
    provides: list[str] = []

    @abstractmethod
    def get_data(self, city_name: str, lat: float, lon: float) -> dict[str, float]:
        """
        Get data for a city.

        Args:
            city_name: Name of the city.
            lat: Latitude of the city.
            lon: Longitude of the city.

        Returns:
            Dict mapping variable names to values.
        """
        pass

    def initialize(self) -> None:
        """Initialize the data source."""
        pass

    def cleanup(self) -> None:
        """Clean up data source resources."""
        pass


class ScoreModifierPlugin(BasePlugin):
    """
    Base class for score modifier plugins.

    Score modifier plugins can adjust the final score based on custom logic.
    """

    # Order in which modifiers are applied (lower = earlier)
    priority: int = 100

    @abstractmethod
    def modify_score(
        self,
        city_name: str,
        base_score: float,
        variables: dict[str, float],
    ) -> float:
        """
        Modify the score for a city.

        Args:
            city_name: Name of the city.
            base_score: The score before modification.
            variables: All available variables for the city.

        Returns:
            Modified score.
        """
        pass

    def initialize(self) -> None:
        """Initialize the modifier."""
        pass

    def cleanup(self) -> None:
        """Clean up modifier resources."""
        pass


@dataclass
class PluginManager:
    """Manages loading and running plugins."""

    data_sources: list[DataSourcePlugin] = field(default_factory=list)
    score_modifiers: list[ScoreModifierPlugin] = field(default_factory=list)
    _loaded_modules: dict[str, Any] = field(default_factory=dict)

    def get_plugins_dir(self) -> Path:
        """Get the plugins directory."""
        plugins_dir = get_config_dir() / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        return plugins_dir

    def discover_plugins(self) -> list[Path]:
        """Discover plugin files in the plugins directory."""
        plugins_dir = self.get_plugins_dir()
        return list(plugins_dir.glob("*.py"))

    def load_plugin(self, plugin_path: Path) -> list[BasePlugin]:
        """
        Load a plugin from a Python file.

        Args:
            plugin_path: Path to the plugin file.

        Returns:
            List of plugin instances loaded from the file.
        """
        spec = importlib.util.spec_from_file_location(
            f"city_compare_plugin_{plugin_path.stem}",
            plugin_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load plugin: {plugin_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        self._loaded_modules[plugin_path.stem] = module

        # Find plugin classes in the module
        plugins: list[BasePlugin] = []
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BasePlugin)
                and obj not in (BasePlugin, DataSourcePlugin, ScoreModifierPlugin)
            ):
                plugin_instance = obj()
                plugins.append(plugin_instance)

        return plugins

    def load_all_plugins(self) -> None:
        """Load all plugins from the plugins directory."""
        for plugin_path in self.discover_plugins():
            try:
                plugins = self.load_plugin(plugin_path)
                for plugin in plugins:
                    plugin.initialize()
                    if isinstance(plugin, DataSourcePlugin):
                        self.data_sources.append(plugin)
                    elif isinstance(plugin, ScoreModifierPlugin):
                        self.score_modifiers.append(plugin)
            except Exception as e:
                print(f"Warning: Failed to load plugin {plugin_path}: {e}")

        # Sort score modifiers by priority
        self.score_modifiers.sort(key=lambda p: p.priority)

    def get_extra_data(
        self,
        city_name: str,
        lat: float,
        lon: float,
    ) -> dict[str, float]:
        """
        Get extra data from all data source plugins.

        Args:
            city_name: Name of the city.
            lat: Latitude.
            lon: Longitude.

        Returns:
            Combined data from all plugins.
        """
        data: dict[str, float] = {}
        for plugin in self.data_sources:
            try:
                plugin_data = plugin.get_data(city_name, lat, lon)
                data.update(plugin_data)
            except Exception as e:
                print(f"Warning: Plugin {plugin.name} failed: {e}")
        return data

    def apply_score_modifiers(
        self,
        city_name: str,
        score: float,
        variables: dict[str, float],
    ) -> float:
        """
        Apply all score modifiers.

        Args:
            city_name: Name of the city.
            score: Base score.
            variables: All variables.

        Returns:
            Modified score.
        """
        for modifier in self.score_modifiers:
            try:
                score = modifier.modify_score(city_name, score, variables)
            except Exception as e:
                print(f"Warning: Score modifier {modifier.name} failed: {e}")
        return score

    def list_plugins(self) -> list[PluginMetadata]:
        """List all loaded plugins."""
        plugins: list[PluginMetadata] = []
        for plugin in self.data_sources + self.score_modifiers:
            plugins.append(plugin.get_metadata())
        return plugins

    def cleanup(self) -> None:
        """Clean up all plugins."""
        for plugin in self.data_sources + self.score_modifiers:
            try:
                plugin.cleanup()
            except Exception:
                pass


# Global plugin manager instance
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager, initializing if needed."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.load_all_plugins()
    return _plugin_manager


def register_plugin(cls: type[BasePlugin]) -> type[BasePlugin]:
    """
    Decorator to register a plugin class.

    This is a no-op decorator that just marks a class as a plugin.
    The actual registration happens when the module is loaded.
    """
    return cls


# Example plugins (can be used as templates)
EXAMPLE_DATA_SOURCE = '''"""Example data source plugin for city-compare."""

from city_compare.plugins import DataSourcePlugin, register_plugin


@register_plugin
class ExampleDataPlugin(DataSourcePlugin):
    """Example plugin that provides mock data."""

    name = "example_data"
    description = "Example data source plugin"
    version = "1.0.0"
    author = "Your Name"
    provides = ["example_score", "example_value"]

    def get_data(self, city_name: str, lat: float, lon: float) -> dict[str, float]:
        """Return example data for any city."""
        return {
            "example_score": 50.0,
            "example_value": lat + lon,  # Just an example calculation
        }
'''

EXAMPLE_SCORE_MODIFIER = '''"""Example score modifier plugin for city-compare."""

from city_compare.plugins import ScoreModifierPlugin, register_plugin


@register_plugin
class BonusModifier(ScoreModifierPlugin):
    """Adds a bonus to cities starting with 'P'."""

    name = "p_city_bonus"
    description = "Adds bonus points to cities starting with P"
    version = "1.0.0"
    author = "Your Name"
    priority = 50  # Lower = earlier

    def modify_score(
        self,
        city_name: str,
        base_score: float,
        variables: dict[str, float],
    ) -> float:
        """Add 10 points bonus for P cities."""
        if city_name.upper().startswith("P"):
            return base_score + 10
        return base_score
'''
