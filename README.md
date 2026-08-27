# win2cape

Convert a **Windows cursor pack** (`.ani` / `.cur`) into a **macOS Mousecape `.cape`** — and
actually get the *main pointer* to change on **macOS 26 (Tahoe)**, which Mousecape alone can't do.

Animation, hotspots, and transparency are all preserved.

---

## The short version

If you've tried to theme your cursor on macOS 26 and found that **every cursor changes except
the main arrow**, this repo explains why and fixes it.

macOS 26 renders the primary pointer through the identifier `com.apple.coregraphics.ArrowS`
(and the text cursor through `com.apple.coregraphics.IBeamS`). Mousecape's identifier table
was last updated in 2020 and only knows `com.apple.coregraphics.Arrow` / `.IBeam`. Registering
those on Tahoe **silently does nothing** — `mousecloak` even prints `Applied successfully!`
while the pointer stays stock.

I couldn't find these identifiers documented anywhere, so this repo writes them down.

---

## Credits — the artwork is not mine

This tool was built while converting a **ZUTOMAYO** cursor theme created by **乱涂乱画BEN**.

**The original pack is not redistributed here.** Get it from the artist:
👉 **https://ko-fi.com/s/22841fd8b0**

Please support the original creator. This repo ships only the converter and the setup
scripts — bring your own cursor pack.

`mousecloak` is part of [Mousecape](https://github.com/alexzielenski/Mousecape) by Alex
Zielenski (MIT). It is not bundled here either; the installer locates your copy.

---

## Requirements

- macOS (tested on **macOS 26 / Tahoe**, Apple Silicon)
- Python 3 with Pillow — `pip3 install Pillow`
- [Mousecape](https://github.com/alexzielenski/Mousecape/releases) — only for its bundled
  `mousecloak` CLI. You never need to open the app.

> `mousecloak` is x86_64-only, so on Apple Silicon it runs under Rosetta 2. It is validly
> code-signed (Team ID `3GD8ABJ22W`).

---

## Usage

**1. Convert your pack**

```sh
python3 ani2cape.py /path/to/windows-cursor-folder --name "My Theme" -o MyTheme.cape
```

```
  Normal.ani           -> normal        2 id(s)  8 frame(s)
  Link.ani             -> link          2 id(s)  8 frame(s)
  ...
  skipped (no macOS equivalent): Handwriting.ani, Person.cur, Pin.cur

Wrote MyTheme.cape - 42 cursor identifiers, 313 KB
```

**2. Install it so it survives reboots**

```sh
cd install
./install.sh ../MyTheme.cape 1.15     # second argument is cursor size; 1.0 = original
```

That installs a **per-user LaunchAgent**. No root, no admin password, no privileged daemon —
just a plist in `~/Library/LaunchAgents` you own.

**3. Uninstall**

```sh
cd install && ./uninstall.sh
```

Your pre-existing cursors are backed up to
`~/Library/Application Support/CursorCape/original-cursors-backup.cape` during install.

---

## Making the cursor bigger

```sh
mousecloak --scale 1.15      # 15% larger; 1.0 restores original
```

Prefer this over resampling the source art. The generated cape ships a 2× (64px)
representation, so macOS scales *down* from the larger image and stays sharp — whereas
upscaling 32px art to ~38px just looks blurry.

Scale is a **per-session** setting and resets at logout, which is why `apply-cursor.sh`
re-applies it at every login. Edit `SCALE` at the top of that script to change it.

---

## How it works (the two hard parts)

### 1. Pillow silently drops cursor transparency

Pillow opens `.cur` frames without error — but **every pixel comes back opaque**. Windows
cursors store transparency in a separate **1-bpp AND mask** appended after the color data,
which Pillow's `CurImagePlugin` does not apply here. Trust it and every cursor renders as a
white box.

`decode_icon()` parses the DIB directly: it reads `BITMAPINFOHEADER`, walks the bottom-up rows
(`biHeight` is *double* the real height because the XOR image and AND mask are stacked), and
sets alpha to 0 wherever a mask bit is set.

```
transparent pixels via Pillow      :    0 / 1024   <- wrong
transparent pixels via decode_icon :  345 / 1024   <- correct
```

### 2. The main pointer wouldn't change on macOS 26

Applying the cape replaced 38 of 40 cursors. Only `Arrow` and `IBeam` stayed stock — the two
you look at most.

Ruling things out:

- **Not animation.** A single-frame arrow was rejected too.
- **Not a bad identifier.** `com.apple.coregraphics.Arrow` is correct — it's what
  `mousecloak --dump` reports for the live pointer.
- **Not a silent error.** `mousecloak` reported success. `--dump` showed the stock 28×40
  Apple arrow regardless.

A blog claimed Tahoe used "S-variant" identifiers, with no specifics, and the relevant
Mousecape issue was unanswered. So rather than guess, search the OS itself:

```sh
strings -a /System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_arm64e.01 \
  | grep -aoE 'com\.apple\.(coregraphics|cursor)\.[A-Za-z0-9_]+' | sort -u
```

```
com.apple.coregraphics.Arrow
com.apple.coregraphics.ArrowS      <- new in macOS 26
com.apple.coregraphics.IBeam
com.apple.coregraphics.IBeamS      <- new in macOS 26
...
```

Exactly two S-variants exist, and they correspond exactly to the two cursors that failed.
Adding them to the cape makes the main pointer change.

> **Why `mousecloak --dump` can't reveal this:** it iterates its own hardcoded 2020 identifier
> list, so it can never show an identifier Apple added later. The dyld shared cache is the
> source of truth.

---

## Cursor mapping

Windows roles are matched from filenames (with common aliases) and fanned out to every macOS
cursor that should share that art — so you don't get stock cursors leaking through mid-drag.

| Windows role | macOS identifiers |
|---|---|
| Normal | `coregraphics.Arrow`, `coregraphics.ArrowS` |
| Text | `coregraphics.IBeam`, `coregraphics.IBeamS`, `IBeamXOR`, `cursor.26` |
| Link | `cursor.2`, `cursor.13` |
| Move | `coregraphics.Move`, `cursor.11`, `cursor.12` |
| Busy | `coregraphics.Wait`, `cursor.4` |
| Working | `cursor.14`, `cursor.15`, `cursor.16` |
| Precision | `cursor.7`, `cursor.8`, `cursor.41`, `cursor.20` |
| Unavailable | `cursor.3` |
| Help | `cursor.40` |
| Alternate | `coregraphics.ArrowCtx`, `cursor.24` |
| Vertical | `cursor.23`, `.32`, `.21`, `.22`, `.31`, `.36` |
| Horizontal | `cursor.19`, `.28`, `.17`, `.18`, `.38`, `.27` |
| Diagonal1 (NW-SE) | `cursor.34`, `.33`, `.35` |
| Diagonal2 (NE-SW) | `cursor.30`, `.29`, `.37` |

Base identifiers come from Mousecape's `cursorMap()` in `mousecloak/MCDefs.m`.

**Skipped:** Handwriting, Person, and Pin have no macOS equivalent.

> If a pack ships an `install.inf`, it's the authoritative source for which file is which role —
> that's how the `SizeNWSE` = Diagonal1 / `SizeNESW` = Diagonal2 assignment was confirmed here.

---

## Caveats

- **`ArrowS` is private API.** A future macOS update could rename it and break the main
  pointer again. Re-run the `strings` command above to find the new name.
- **Brief stock cursor at login.** The agent waits ~5s for the GUI session before applying.
- **Rosetta dependency.** `mousecloak` is x86_64-only; if Apple drops Rosetta, this stops working.
- **Not all packs map cleanly.** Unrecognised filenames are reported and skipped, not guessed at.

---

## License

MIT for the code in this repository. **This does not cover any cursor artwork you convert**,
which remains the property of its original creator.
