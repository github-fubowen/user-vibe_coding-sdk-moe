## [2026-08-22] pytest 在沙箱 myenv 下报 AttributeError: __spec__

- 环境: WorkBuddy 沙箱 + `<PY_ENV>`（系统 Python myenv，pytest）
- 确定性阶段命中: 签名匹配（error-sig.py sig-py-shim）
- 轨迹: verify-runner.py 冒烟 → pytest -V 报 `_pytest.config.MyOptionParser(py.std.argparse.ArgumentParser)` → AttributeError: __spec__（py._apipkg 导入损坏）→ 判定为环境 shim 干扰而非脚本缺陷
- 修复: 脚本自身 stdlib 零依赖不受影响；被探测工具报错属预期降级（ref-19 §6-3）
- 验证: FAILED（环境侧，非脚本）——verify-runner 正确透传 exit 1 + 有界 tail；通过路径用 `python -c "print('ok')"` 复测 ALL PASS
- 教训: 沙箱 PYTHONPATH + sitecustomize.py shim 会破坏系统 python 的第三方包；凡"脚本自己没问题但工具报诡异错"先查 env
