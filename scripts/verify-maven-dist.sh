#!/bin/sh
# Verifies the Maven distribution pinned in backend/.mvn/wrapper/maven-wrapper.properties against
# checksums published by Apache. Run inside the backend toolchain container (needs curl, sha256sum, sha512sum).
set -u
PROPS=/workspace/backend/.mvn/wrapper/maven-wrapper.properties
URL=$(sed -n 's/^distributionUrl=//p' "$PROPS" | tr -d '\r')
PINNED=$(sed -n 's/^distributionSha256Sum=//p' "$PROPS" | tr -d '\r')
NAME=${URL##*/}
VERSION=$(echo "$NAME" | sed 's/^apache-maven-\(.*\)-bin\.zip$/\1/')
TMP=$(mktemp -d)
echo "distributionUrl:        $URL"
echo "pinned SHA-256:         $PINNED"
echo "unzip available:        $(command -v unzip || echo NO - wrapper would download .tar.gz instead)"

curl -fsSL -o "$TMP/$NAME" "$URL" || { echo "FAIL: download of $URL"; exit 1; }
echo "downloaded bytes:       $(wc -c < "$TMP/$NAME")"
unzip -tq "$TMP/$NAME" >/dev/null && echo "zip integrity:          OK" || { echo "FAIL: zip is corrupt"; exit 1; }
ACT256=$(sha256sum "$TMP/$NAME" | cut -d' ' -f1)
ACT512=$(sha512sum "$TMP/$NAME" | cut -d' ' -f1)
echo "actual SHA-256:         $ACT256"
echo "actual SHA-512:         $ACT512"

status=0
central=$(curl -fsSL "$URL.sha512" | tr -d '\r\n ' | cut -c1-128)
echo "Maven Central SHA-512:  $central"
[ "$central" = "$ACT512" ] && echo "  match: Maven Central" || { echo "  MISMATCH vs Maven Central"; status=1; }

apache=""
for base in https://downloads.apache.org https://archive.apache.org/dist; do
  apache=$(curl -fsSL "$base/maven/maven-3/$VERSION/binaries/$NAME.sha512" 2>/dev/null | tr -d '\r\n ' | cut -c1-128)
  if [ -n "$apache" ]; then echo "apache.org SHA-512:     $apache ($base)"; break; fi
done
if [ -z "$apache" ]; then echo "  could not fetch the apache.org checksum"; status=1
elif [ "$apache" = "$ACT512" ]; then echo "  match: apache.org"; else echo "  MISMATCH vs apache.org"; status=1; fi

[ "$PINNED" = "$ACT256" ] && echo "pinned SHA-256:         MATCHES the verified distribution" \
  || { echo "pinned SHA-256:         MISMATCH (pinned $PINNED, actual $ACT256)"; status=1; }

echo "wrapper cache:"
ls -la /root/.m2/wrapper/dists/ 2>/dev/null || echo "  (empty)"
rm -rf "$TMP"
exit $status
