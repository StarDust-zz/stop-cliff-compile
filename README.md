# stop-cliff-compile

Synergy deep-dive: long-horizon agent **horizon gate** joining
[stop-dont-drift](https://github.com/StarDust-zz/stop-dont-drift),
[cliff-dont-drift](https://github.com/StarDust-zz/cliff-dont-drift),
and [compile-dont-inject](https://github.com/StarDust-zz/compile-dont-inject)
into one measurable `continue | cliff | stop` action.

## Run

```bash
python3 experiment.py
```

Expect `7/7 assertions passed`, exit 0.

Stdlib only. No network, GPU, or vendor API in the 7/7 path.

## Layout

| File | Role |
|------|------|
| `experiment.py` | Horizon gate + 7 join assertions |
| `stop_stub.py` | Principled stop algebra (from stop-dont-drift) |
| `cliff_stub.py` | Cliff truncate+signature (from cliff-dont-drift) |
| `compile_stub.py` | Brief-State compile vs AMMI (from compile-dont-inject) |
| `DESCRIPTION.md` | Claim, falsifier, object algebra, synergy |
| `KEEPERS.txt` | What is now object vs still hunch |

## License

MIT — see [LICENSE](LICENSE).
