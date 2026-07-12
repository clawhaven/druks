from druks.extensions import Extension


class Usage(Extension):
    name = "usage"
    icon = "gauge"
    description = "Harness usage metering — polls the CLIs' quota and spend."
