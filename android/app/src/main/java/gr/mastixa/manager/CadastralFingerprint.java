package gr.mastixa.manager;

import java.nio.*;
import java.nio.charset.*;
import java.security.*;

/** Pure Java shared fingerprint framing, independent of Android/JSON/locale.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralFingerprint {
    private CadastralFingerprint() {}
    public static String fingerprint(Object... fields) {
        try {
            MessageDigest hash=MessageDigest.getInstance("SHA-256");
            for(Object field:fields) {
                byte[] data;
                if(field==null)data=null;
                else if(field instanceof byte[])data=(byte[])field;
                else if(field instanceof String) {
                    ByteBuffer encoded=StandardCharsets.UTF_8.newEncoder().onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT).encode(java.nio.CharBuffer.wrap((String)field));
                    data=new byte[encoded.remaining()];encoded.get(data);
                }else throw new IllegalArgumentException("Exact text/bytes/null required");
                hash.update(ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN).putInt(data==null?-1:data.length).array());
                if(data!=null)hash.update(data);
            }
            StringBuilder text=new StringBuilder();for(byte b:hash.digest())text.append(Character.forDigit((b>>>4)&15,16)).append(Character.forDigit(b&15,16));return text.toString();
        }catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}
         catch(CharacterCodingException e){throw new IllegalArgumentException("Invalid UTF-8 text",e);}
    }
}
