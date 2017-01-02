# tv

Script on top of youtube-dl to manage downloads of podcasts and TV shows.

## Usage

```bash
$ tv download
$ tv archive [--keep] [<filename>]
$ tv list
```

## Configuration

A configuration file should be created in `~/.config/tv.yaml`, matching the format of the example file `tv.yaml`.

New provides can be created by subclassing the `Show` class.
