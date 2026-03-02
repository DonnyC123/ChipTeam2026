class GenericChecker:
    def __init__(self, fatal=True):
        self.fatal = fatal

    def check_len(self, expected_queue, actual_queue):
        if expected_queue.qsize() != actual_queue.qsize():
            msg = (
                f"Mismatch in queue lengths: "
                f"model={expected_queue.qsize()}, "
                f"monitor={actual_queue.qsize()}"
            )
            if self.fatal:
                raise RuntimeError(msg)
            else:
                print(f"[WARNING] {msg}")

    async def check_output(self, expected_queue, actual_queue):
        while (not expected_queue.empty()) and (not actual_queue.empty()):
            monitor_out = await actual_queue.get()
            model_out = await expected_queue.get()

            if monitor_out != model_out:
                msg = f""""Mismatch in model and monitor outputs:
          model output={model_out},
          monitor output={monitor_out}"""
                if self.fatal:
                    raise RuntimeError(msg)
                else:
                    print(f"[WARNING] {msg}")

    async def check_output_error_tol(self, expected_queue, actual_queue, error_tol):
        num_results = min(actual_queue.qsize(), expected_queue.qsize())
        num_error = 0
        while (not expected_queue.empty()) and (not actual_queue.empty()):
            monitor_out = await actual_queue.get()
            model_out = await expected_queue.get()
            if monitor_out != model_out:
                num_error += 1

        error = num_error / num_results
        if error > error_tol:
            msg = f"Error rate {error} not within error tolerance of {error_tol}"
            if self.fatal:
                raise RuntimeError(msg)
            else:
                print(f"[WARNING] {msg}")
        else:
            msg = f"Error rate {error} within error tolerance of {error_tol}"
            print(msg)

    async def check_remaining(self, output_queue, queue_name=""):
        while not output_queue.empty():
            output = await output_queue.get()
            msg = f"No corresponding output for {queue_name} output ={output}"
            if self.fatal:
                raise RuntimeError(msg)
            else:
                print(f"[WARNING] {msg}")

    async def check(self, expected_queue, actual_queue):
        self.check_len(expected_queue, actual_queue)
        await self.check_output(expected_queue, actual_queue)
        await self.check_remaining(expected_queue, "expected")
        await self.check_remaining(actual_queue, "actual")

    async def check_with_error_tol(self, expected_queue, actual_queue, error_tol):
        self.check_len(expected_queue, actual_queue)
        await self.check_output_error_tol(expected_queue, actual_queue, error_tol)
        await self.check_remaining(expected_queue, "expected")
        await self.check_remaining(actual_queue, "actual")
