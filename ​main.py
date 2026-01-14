Niyetini tut dediğinde 3den geriye saysın o sayarken niyetini tut yazısı tamamen kaybolmayacak şekilde yanıp sönsün yani pulse efekti gibi
üst solda totem yap değil totemci yazsın 
öneri alanının ismi Totem Öner olsun bize iletebileceği bir text box olsun buraya totemini yazabilsin.  Altında da altın bu totemi yaptığında %kaç tutuyor gibi bir alan olsun oraya rakam yazabilsin. harf ve özel karakter kullanımı yasak olacak bu alanda.





import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() => runApp(MaterialApp(
      home: MainStructure(),
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        primarySwatch: Colors.indigo,
        scaffoldBackgroundColor: Colors.white,
      ),
    ));

// --- HAFIZA VE GLOBAL DEĞİŞKENLER ---
List<Map<String, dynamic>> userTotems = [];
int userRights = 5;

// --- ANA YAPI (SCAFFOLD VE TAB YÖNETİMİ) ---
class MainStructure extends StatefulWidget {
  @override
  _MainStructureState createState() => _MainStructureState();
}

class _MainStructureState extends State<MainStructure> with SingleTickerProviderStateMixin {
  bool isProfileMode = false;
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 1,
        leading: Padding(
          padding: const EdgeInsets.all(8.0),
          child: GestureDetector(
            onTap: () => setState(() => isProfileMode = !isProfileMode),
            child: CircleAvatar(
              backgroundColor: Colors.indigo,
              child: Icon(isProfileMode ? Icons.auto_awesome : Icons.person, color: Colors.white),
            ),
          ),
        ),
        title: Text("TOTEMCİ", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
      ),
      body: isProfileMode 
          ? ProfileScreen(tabController: _tabController) 
          : TotemScreen(onOutOfRights: () {
              setState(() {
                isProfileMode = true;
                _tabController.animateTo(3); 
              });
            }),
    );
  }
}

// --- TOTEM YAPMA EKRANI (DİNAMİK LİSTE VE ANİMASYONLAR) ---
class TotemScreen extends StatefulWidget {
  final VoidCallback onOutOfRights;
  TotemScreen({required this.onOutOfRights});

  @override
  _TotemScreenState createState() => _TotemScreenState();
}

class _TotemScreenState extends State<TotemScreen> with SingleTickerProviderStateMixin {
  List<String> allTotems = []; 
  String screenText = "YÜKLENİYOR...";
  bool isLoading = true;
  bool isLocked = false;
  bool isSpinning = false;
  bool totemFinished = false;
  int countdown = 5;
  Timer? timer;
  
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _loadFirebaseSim();
    _pulseController = AnimationController(vsync: this, duration: Duration(milliseconds: 1200))..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.1, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut)
    );
  }

  // Firebase totemLibrary simülasyonu
  void _loadFirebaseSim() async {
    await Future.delayed(Duration(seconds: 1)); 
    setState(() {
      allTotems = [
        "Masaya parmak uçlarınla dokun",
        "Omuzlarını bir kere silkele",
        "Telefonu düz bir zemine koy",
        "Saate bakıp kafanı salla",
        "Gözlerini kapat ve derin nefes al",
        "Kendi kendine gülümse"
      ];
      isLoading = false;
      screenText = "TOTEM YAP";
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    timer?.cancel();
    super.dispose();
  }

  void startTotem() {
    if (userRights <= 0) {
      widget.onOutOfRights();
      return;
    }
    setState(() { 
      isLocked = true; 
      totemFinished = false;
      countdown = 5;
    });
    
    Timer.periodic(Duration(seconds: 1), (t) {
      if (countdown > 1) {
        setState(() => countdown--);
      } else {
        t.cancel();
        startSpinning();
      }
    });
  }

  void startSpinning() {
    setState(() { isSpinning = true; });
    timer = Timer.periodic(Duration(milliseconds: 70), (t) {
      setState(() { 
        screenText = allTotems[Random().nextInt(allTotems.length)]; 
      });
    });
  }

  void stopTotem() {
    if (isSpinning) {
      timer?.cancel();
      setState(() {
        isSpinning = false;
        isLocked = false;
        totemFinished = true;
        userRights--; 
        userTotems.add({"title": screenText, "status": "Bekliyor"});
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) return Center(child: CircularProgressIndicator());

    return GestureDetector(
      onTap: isSpinning ? stopTotem : null,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: double.infinity, height: double.infinity, color: Colors.white,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text("Kalan Hakkın: $userRights", style: TextStyle(color: Colors.grey, letterSpacing: 1.1)),
            SizedBox(height: 50),
            if (isLocked && !isSpinning) ...[
              FadeTransition(
                opacity: _pulseAnimation,
                child: Text("Niyetini tut.", 
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.w300, color: Colors.indigo, letterSpacing: 2)),
              ),
              SizedBox(height: 30),
              Text("$countdown", style: TextStyle(fontSize: 90, fontWeight: FontWeight.bold, color: Colors.indigo)),
            ] else ...[
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 40),
                child: Text(screenText, textAlign: TextAlign.center, 
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
              ),
            ],
            SizedBox(height: 40),
            if (!isLocked && !isSpinning && !totemFinished)
              ElevatedButton(
                onPressed: startTotem, 
                child: Text("BAŞLA", style: TextStyle(letterSpacing: 1.5)),
                style: ElevatedButton.styleFrom(padding: EdgeInsets.symmetric(horizontal: 40, vertical: 15)),
              ),
            if (isSpinning) 
              Text("Durdurmak için EKRANA dokun!", style: TextStyle(color: Colors.orange, fontWeight: FontWeight.bold)),
            if (totemFinished) ...[
              Text("Profilinden sonucu girebilirsin.", style: TextStyle(color: Colors.grey)),
              SizedBox(height: 20),
              ElevatedButton(
                onPressed: () => setState(() { totemFinished = false; screenText = "TOTEM YAP"; }),
                child: Text("YENİ TOTEM YAP"),
                style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
              ),
            ]
          ],
        ),
      ),
    );
  }
}

// --- PROFİL, ANALİZ VE ÖNERİ EKRANI ---
class ProfileScreen extends StatefulWidget {
  final TabController tabController;
  ProfileScreen({required this.tabController});
  @override
  _ProfileScreenState createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final TextEditingController _totemController = TextEditingController();
  final TextEditingController _rateController = TextEditingController();
  bool _isButtonEnabled = false;

  @override
  void initState() {
    super.initState();
    _totemController.addListener(_validateFields);
    _rateController.addListener(_validateFields);
  }

  void _validateFields() {
    setState(() {
      _isButtonEnabled = _totemController.text.length >= 15 && 
                         _totemController.text.length <= 300 && 
                         _rateController.text.isNotEmpty;
    });
  }

  @override
  void dispose() {
    _totemController.dispose();
    _rateController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    int total = userTotems.length;
    int success = userTotems.where((t) => t["status"] == "Tuttu").length;
    int failed = userTotems.where((t) => t["status"] == "Tutmadı").length;
    double rate = (success + failed) == 0 ? 0 : (success / (success + failed));

    return Column(
      children: [
        TabBar(
          controller: widget.tabController,
          isScrollable: true, labelColor: Colors.indigo,
          tabs: [Tab(text: "Totemlerim"), Tab(text: "Analiz"), Tab(text: "Totem Öner"), Tab(text: "Satın Al")],
        ),
        Expanded(
          child: TabBarView(
            controller: widget.tabController,
            children: [
              // 1. Totemlerim Listesi
              userTotems.isEmpty 
              ? Center(child: Text("Henüz totem yapmadın."))
              : ListView.builder(
                itemCount: userTotems.length,
                itemBuilder: (c, i) => Card(
                  margin: EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  child: ListTile(
                    title: Text(userTotems[i]["title"]),
                    trailing: userTotems[i]["status"] == "Bekliyor" 
                      ? Row(mainAxisSize: MainAxisSize.min, children: [
                          IconButton(icon: Icon(Icons.check_circle, color: Colors.green), onPressed: () => setState(() => userTotems[i]["status"] = "Tuttu")),
                          IconButton(icon: Icon(Icons.cancel, color: Colors.red), onPressed: () => setState(() => userTotems[i]["status"] = "Tutmadı")),
                        ]) : Icon(userTotems[i]["status"] == "Tuttu" ? Icons.check_circle : Icons.cancel, color: Colors.grey),
                  ),
                ),
              ),
              // 2. Analiz (Dairesel Grafik)
              Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                Stack(alignment: Alignment.center, children: [
                  SizedBox(width: 150, height: 150, child: CircularProgressIndicator(value: rate, strokeWidth: 12, color: Colors.green, backgroundColor: Colors.red[50])),
                  Text("%${(rate * 100).toInt()}", style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
                ]),
                SizedBox(height: 20),
                Text("Toplam $total Totem Tamamlandı", style: TextStyle(color: Colors.grey)),
              ]),
              // 3. Totem Öner (Dinamik Yeşil Buton)
              Padding(
                padding: EdgeInsets.all(20),
                child: SingleChildScrollView(
                  child: Column(children: [
                    TextField(
                      controller: _totemController,
                      maxLength: 300,
                      maxLines: 3,
                      decoration: InputDecoration(labelText: "Totem Öneriniz", border: OutlineInputBorder(), helperText: "Min 15, Max 300 karakter"),
                    ),
                    SizedBox(height: 20),
                    TextField(
                      controller: _rateController,
                      keyboardType: TextInputType.number,
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly, _MaxPercentFormatter()],
                      decoration: InputDecoration(labelText: "Başarı Oranı", prefixText: "%", border: OutlineInputBorder()),
                    ),
                    SizedBox(height: 30),
                    ElevatedButton(
                      onPressed: _isButtonEnabled ? () {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: Colors.green, content: Text("Öneriniz gönderildi!")));
                        _totemController.clear(); _rateController.clear();
                        FocusScope.of(context).unfocus();
                      } : null,
                      child: Text("GÖNDER", style: TextStyle(fontWeight: FontWeight.bold)),
                      style: ElevatedButton.styleFrom(
                        padding: EdgeInsets.symmetric(horizontal: 60, vertical: 15),
                        backgroundColor: _isButtonEnabled ? Colors.green : Colors.grey[300],
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ]),
                ),
              ),
              // 4. Satın Al
              Center(child: Text("Sınırsız Paket: 99.90 TL", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))),
            ],
          ),
        ),
      ],
    );
  }
}

// Yüzde Kısıtlayıcı
class _MaxPercentFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    if (newValue.text.isEmpty) return newValue;
    int? value = int.tryParse(newValue.text);
    if (value == null) return oldValue;
    if (value > 100) return TextEditingValue(text: '100', selection: TextSelection.collapsed(offset: 3));
    return newValue;
  }
}
