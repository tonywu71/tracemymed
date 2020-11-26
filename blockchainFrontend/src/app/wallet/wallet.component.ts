import { THIS_EXPR } from '@angular/compiler/src/output/output_ast';
import { Component, OnInit } from '@angular/core';
import { HttpClientService } from '../http-client.service';


@Component({
  selector: 'app-wallet',
  templateUrl: './wallet.component.html',
  styleUrls: ['./wallet.component.css']
})
export class WalletComponent implements OnInit {

  publicKey : string = "";
  privateKey : string = "";
  generated : any;
  alreadyWallet : boolean = false;


  constructor(private http : HttpClientService) { }

  saveKeys(){
    localStorage['publicKey'] = this.publicKey
    localStorage['privateKey'] = this.privateKey
    this.alreadyWallet = false
  }

  changeAlreadyWallet(bool){
    this.alreadyWallet = bool;
    console.log("changed alreadyWallet" + this.alreadyWallet)
  }

  ngOnInit(): void {
    this.publicKey = localStorage.getItem('publicKey')
    this.privateKey = localStorage.getItem('privateKey')
    this.generated = localStorage.getItem('generated')
  }

  changeGenWallet(bool){
    localStorage['publicKey'] = bool;
  }

  getKeys(){
    this.http.getKeys().subscribe(
          keys => {
            console.log("keys " + keys.privateKey)
            localStorage['publicKey'] = keys.publicKey;
            this.publicKey= keys.publicKey;
            console.log(localStorage['publicKey'])
            localStorage['privateKey'] = keys.privateKey;
            this.privateKey= keys.privateKey;

          }
        )
  }

  generateKeys():void{
    if (this.generated === false || this.generated === null){
      this.getKeys();

      localStorage['generated'] = true;
      this.generated = localStorage.getItem('generated');

      // this.keys = this.http.getKeys();     

    }
    else{
      alert("Keys already generated");
    }
    
  }

}
