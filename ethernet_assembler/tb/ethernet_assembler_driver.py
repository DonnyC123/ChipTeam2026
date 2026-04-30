from dataclasses import fields, is_dataclass

from tb_utils.generic_drivers import GenericDriver


class EthernetAssemblerDriver(GenericDriver):
    MODEL_ONLY_FIELDS = frozenset({"no_valid_data", "drop_frame"})

    async def recursive_drive(self, input_parent, item):
        for f in fields(item):
            # These fields are metadata for the model and are not DUT inputs.
            if f.name in self.MODEL_ONLY_FIELDS:
                continue

            field_name = f.name
            value = getattr(item, field_name)

            if hasattr(input_parent, field_name):
                signal_or_interface = getattr(input_parent, field_name)
                if is_dataclass(value):
                    await self.recursive_drive(signal_or_interface, value)
                else:
                    signal_or_interface.value = value
            else:
                raise AttributeError(
                    f"Field '{field_name}' found in sequence item "
                    f"but NOT in DUT handle '{input_parent._name}'."
                )
