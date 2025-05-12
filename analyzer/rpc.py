from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import shlex
import traceback
app = FastAPI()


class RunRequest(BaseModel):
    cmd: str

class RunResponse(BaseModel):
    returncode: int
    stdout: str
    stderr: str

@app.post("/run", response_model=RunResponse)
async def run_cli(req: RunRequest):
    try:
        proc = subprocess.run(
            req.cmd,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=3000
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Command timed out")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Failed to run command: {e}")

    return RunResponse(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )

