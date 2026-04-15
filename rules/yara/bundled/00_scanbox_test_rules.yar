rule scanbox_test_suspicious_marker : suspicious
{
  meta:
    title = "ScanBox suspicious marker"
    description = "Matches a harmless local test marker."
    severity = "medium"
    confidence = "medium"
    category = "suspicious"

  strings:
    $marker = "SCANBOX_SUSPICIOUS_MARKER" ascii wide

  condition:
    $marker
}

rule scanbox_test_eicar_marker : malicious
{
  meta:
    title = "ScanBox EICAR test marker"
    description = "Matches the EICAR antivirus test string."
    severity = "high"
    confidence = "high"
    category = "malicious"
    malicious = true

  strings:
    $eicar = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*" ascii

  condition:
    $eicar
}
